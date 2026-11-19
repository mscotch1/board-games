/*
 * The computer player's search, in C: move generation and iterative-deepening alpha-beta.
 *
 * This is a port of rules.legal_turns/apply_turn and the Searcher in ai.py, and it must agree
 * with them: tests/test_native.py compares its legal turns with rules.py on many positions and
 * its scores with ai.Searcher. The board geometry and the evaluation weights are handed over
 * by Python (see native_search.py), so the rules about the shape of the board live only there.
 *
 * Build: see native/Makefile. Nothing here needs more than a C99 compiler and libc.
 */

#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L /* for clock_gettime */
#endif

#include <setjmp.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#define EXPORT __declspec(dllexport)
static int64_t now_ms(void) {
    LARGE_INTEGER f, t;
    QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&t);
    return (int64_t)(t.QuadPart * 1000 / f.QuadPart);
}
#else
#include <time.h>
#define EXPORT __attribute__((visibility("default")))
static int64_t now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}
#endif

#define MAXSQ 256       /* squares on the biggest board (Camelot has 192) */
#define MAXJ 16         /* captures in one turn */
#define MAXMOVES 4096   /* turns in one position (a sparse Camelot board can have over a thousand) */
#define MAXPLY 40
#define WIN 100000
#define NONE INT32_MIN
#define CHECK_EVERY 128
#define TT_BITS 19

#define OWNER(p) ((p) <= 2 ? 0 : 1)
#define IS_KNIGHT(p) ((p) != 0 && (p) % 2 == 0)

typedef struct {
    int rows, cols, size;
    int castle_to_win, ends_turn, confine, castle_moves, forced_exit, wins_need_two, draws;
    int adj_n[MAXSQ];
    int16_t adj[MAXSQ][8];
    int jmp_n[MAXSQ];
    int16_t jmp[MAXSQ][8];
    uint8_t is_home[2][MAXSQ]; /* squares of each side's own castle */
    uint8_t is_goal[2][MAXSQ]; /* squares of the castle each side is trying to reach */
    int home_list[2][4], home_n[2];
    int man, knight, goal_bonus;
    int adv[2][MAXSQ]; /* the value of standing on each square, for each side */
} Config;

typedef struct {
    int16_t from, to, nj;
    int16_t j[MAXJ];
} Move;

typedef struct {
    int pieces[2], home[2], value[2];
} Tally;

/* ---- hashing ------------------------------------------------------------------------------- */

static uint64_t ZP[5][MAXSQ], ZSIDE[2], ZCM[2][8];
static int z_ready = 0;

static uint64_t splitmix(uint64_t *x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

EXPORT void ai_init(void) {
    uint64_t seed = 0x5EEDC0FFEE123457ULL;
    int p, s, i;
    if (z_ready) return;
    for (p = 0; p < 5; p++)
        for (s = 0; s < MAXSQ; s++) ZP[p][s] = splitmix(&seed);
    for (i = 0; i < 2; i++) {
        ZSIDE[i] = splitmix(&seed);
        for (s = 0; s < 8; s++) ZCM[i][s] = splitmix(&seed);
    }
    z_ready = 1;
}

/* ---- configuration ------------------------------------------------------------------------- */

EXPORT void *ai_create(int rows, int cols, int castle_to_win, int ends_turn, int confine, int castle_moves,
                       int forced_exit, int wins_need_two, int draws, const int32_t *adj_flat,
                       const int32_t *jmp_flat, const int32_t *home_flat, int man, int knight, int goal_bonus,
                       const int32_t *adv_flat) {
    Config *c = (Config *)calloc(1, sizeof(Config));
    int s, k, side;
    if (!c || rows * cols > MAXSQ) {
        free(c);
        return NULL;
    }
    c->rows = rows;
    c->cols = cols;
    c->size = rows * cols;
    c->castle_to_win = castle_to_win;
    c->ends_turn = ends_turn;
    c->confine = confine;
    c->castle_moves = castle_moves;
    c->forced_exit = forced_exit;
    c->wins_need_two = wins_need_two;
    c->draws = draws;
    c->man = man;
    c->knight = knight;
    c->goal_bonus = goal_bonus;
    for (s = 0; s < c->size; s++) {
        for (k = 0; k < 8; k++) {
            if (adj_flat[s * 8 + k] >= 0) c->adj[s][c->adj_n[s]++] = (int16_t)adj_flat[s * 8 + k];
            if (jmp_flat[s * 8 + k] >= 0) c->jmp[s][c->jmp_n[s]++] = (int16_t)jmp_flat[s * 8 + k];
        }
        for (side = 0; side < 2; side++) c->adv[side][s] = adv_flat[side * c->size + s];
    }
    for (side = 0; side < 2; side++)
        for (k = 0; k < 4; k++) {
            int sq = home_flat[side * 4 + k];
            if (sq >= 0) {
                c->home_list[side][c->home_n[side]++] = sq;
                c->is_home[side][sq] = 1;
                c->is_goal[1 - side][sq] = 1;
            }
        }
    return c;
}

EXPORT void ai_destroy(void *cfg) { free(cfg); }

/* ---- move generation (mirrors rules.legal_turns) ------------------------------------------- */

enum { PH_START, PH_CANTER, PH_JUMP };

typedef struct {
    const Config *c;
    int player, start, knight;
    uint8_t work[MAXSQ];
    uint8_t cantered[MAXSQ];
    int16_t jumped[MAXJ];
    Move *caps, *oth;
    int ncaps, noth;
} Gen;

static void add_move(Gen *g, int capture, int to, int nj) {
    Move *m;
    if (capture) {
        if (g->ncaps >= MAXMOVES) return;
        m = &g->caps[g->ncaps++];
    } else {
        if (g->noth >= MAXMOVES) return;
        m = &g->oth[g->noth++];
    }
    m->from = (int16_t)g->start;
    m->to = (int16_t)to;
    m->nj = (int16_t)nj;
    if (nj) memcpy(m->j, g->jumped, (size_t)nj * sizeof(int16_t));
}

static void visit(Gen *g, int pos, int steps, int phase, int nj) {
    const Config *c = g->c;
    int player = g->player;
    int entered_goal = c->ends_turn && steps > 0 && c->is_goal[player][pos];
    int jl[8], jo[8], njumps = 0, k;

    if (!entered_goal && (phase != PH_CANTER || g->knight)) {
        for (k = 0; k < c->jmp_n[pos]; k++) {
            int landing = c->jmp[pos][k], over = (pos + landing) / 2;
            if (g->work[landing] == 0 && g->work[over] != 0 && OWNER(g->work[over]) != player) {
                jl[njumps] = landing;
                jo[njumps] = over;
                njumps++;
            }
        }
    }

    if (steps > 0) {
        if (phase == PH_JUMP) {
            if (!njumps) add_move(g, 1, pos, nj);
        } else if (pos != g->start) { /* cantering round to where it began would be passing */
            add_move(g, 0, pos, 0);
        }
    }

    if (entered_goal) return;

    for (k = 0; k < njumps && nj < MAXJ; k++) {
        uint8_t taken = g->work[jo[k]];
        g->work[jo[k]] = 0;
        g->jumped[nj] = (int16_t)jo[k];
        visit(g, jl[k], steps + 1, PH_JUMP, nj + 1);
        g->work[jo[k]] = taken;
    }

    if (phase != PH_JUMP) {
        for (k = 0; k < c->jmp_n[pos]; k++) {
            int landing = c->jmp[pos][k], over = (pos + landing) / 2;
            if (g->work[over] != 0 && OWNER(g->work[over]) == player && !g->cantered[over] &&
                g->work[landing] == 0 && !c->is_home[player][landing]) {
                g->cantered[over] = 1;
                visit(g, landing, steps + 1, PH_CANTER, nj);
                g->cantered[over] = 0;
            }
        }
    }

    if (phase == PH_START) {
        for (k = 0; k < c->adj_n[pos]; k++) {
            int step = c->adj[pos][k];
            if (g->work[step] == 0 && !c->is_home[player][step]) add_move(g, 0, step, 0);
        }
    }
}

static void explore(Gen *g, const uint8_t *board, int start, int cm_left) {
    const Config *c = g->c;
    int player = g->player, k;
    uint8_t piece = board[start];

    if (c->confine && c->is_goal[player][start]) {
        /* a piece in the enemy castle can't come out: it may only move to the other castle square */
        if (cm_left > 0) {
            g->start = start;
            for (k = 0; k < c->adj_n[start]; k++) {
                int step = c->adj[start][k];
                if (c->is_goal[player][step] && board[step] == 0) add_move(g, 0, step, 0);
            }
        }
        return;
    }
    g->start = start;
    g->knight = IS_KNIGHT(piece);
    g->work[start] = 0; /* the moving piece is lifted off the board while it travels */
    visit(g, start, 0, PH_START, 0);
    g->work[start] = piece;
}

/* The legal turns for `player`; returns how many, and points *out at them (inside caps or oth). */
static int gen_moves(const Config *c, const uint8_t *board, int player, int cm_used, Move *caps, Move *oth,
                     Move **out) {
    Gen g;
    int cm_left = c->castle_moves - cm_used, i, trapped = 0;
    if (cm_left < 0) cm_left = 0;
    g.c = c;
    g.player = player;
    g.caps = caps;
    g.oth = oth;
    g.ncaps = g.noth = 0;
    memcpy(g.work, board, (size_t)c->size);
    memset(g.cantered, 0, (size_t)c->size);

    if (c->forced_exit) {
        for (i = 0; i < c->home_n[player]; i++) {
            int sq = c->home_list[player][i];
            if (board[sq] && OWNER(board[sq]) == player) {
                trapped = 1;
                explore(&g, board, sq, cm_left);
            }
        }
    }
    if (!trapped) {
        for (i = 0; i < c->size; i++)
            if (board[i] && OWNER(board[i]) == player) explore(&g, board, i, cm_left);
    }
    if (g.ncaps) {
        *out = caps;
        return g.ncaps;
    }
    *out = oth;
    return g.noth;
}

/* For the tests: the legal turns, as from, to, number of captures, captured squares... */
EXPORT int ai_legal_moves(void *cfg, const int32_t *board_in, int player, int cm_used, int32_t *out, int cap) {
    const Config *c = (const Config *)cfg;
    uint8_t board[MAXSQ];
    Move *caps = (Move *)malloc(sizeof(Move) * MAXMOVES * 2), *list;
    int n, i, k, used = 0;
    if (!caps) return -1;
    for (i = 0; i < c->size; i++) board[i] = (uint8_t)board_in[i];
    n = gen_moves(c, board, player, cm_used, caps, caps + MAXMOVES, &list);
    for (i = 0; i < n; i++) {
        if (used + 3 + list[i].nj > cap) {
            free(caps);
            return -2;
        }
        out[used++] = list[i].from;
        out[used++] = list[i].to;
        out[used++] = list[i].nj;
        for (k = 0; k < list[i].nj; k++) out[used++] = list[i].j[k];
    }
    free(caps);
    return n;
}

/* ---- the search (mirrors ai.Searcher) ------------------------------------------------------ */

typedef struct {
    uint64_t key;
    int32_t score;
    uint32_t best;
    int16_t depth;
    int8_t flag; /* 0 exact, 1 lower bound, 2 upper bound */
} TT;

typedef struct {
    int64_t order; /* sorts the turns: the best-known first, then the best-looking */
    int st;        /* the position after the turn, for the side that played it */
    int idx;
    uint32_t mk;
    Move *m;
    Tally after;
    int cm[2];
} Kid;

typedef struct {
    const Config *c;
    int64_t deadline_ms, max_nodes, nodes, expanded;
    int guaranteed, beam;
    jmp_buf jb;
    uint8_t board[MAXPLY][MAXSQ];
    uint64_t hash[MAXPLY];
    Tally tally[MAXPLY];
    int cm[MAXPLY][2];
    Move *mlev[MAXPLY]; /* each level's turn lists (captures, then the others), made when first reached */
    Kid *klev[MAXPLY];
    TT *tt;
    uint64_t ttmask;
} Search;

static uint32_t move_key(const Move *m) {
    uint32_t k = (uint32_t)m->from * 7919u ^ (uint32_t)m->to * 104729u ^ 0x9E3779B9u;
    int i;
    for (i = 0; i < m->nj; i++) k += (uint32_t)(m->j[i] + 1) * 1299709u;
    return k ? k : 1;
}

static Move *level_moves(Search *S, int lv) {
    if (!S->mlev[lv]) {
        S->mlev[lv] = (Move *)malloc(sizeof(Move) * 2 * MAXMOVES);
        if (!S->mlev[lv]) longjmp(S->jb, 2);
    }
    return S->mlev[lv];
}

static Kid *level_kids(Search *S, int lv) {
    if (!S->klev[lv]) {
        S->klev[lv] = (Kid *)malloc(sizeof(Kid) * MAXMOVES);
        if (!S->klev[lv]) longjmp(S->jb, 2);
    }
    return S->klev[lv];
}

static void tick(Search *S) {
    S->nodes++;
    if (S->nodes % CHECK_EVERY || S->guaranteed) return;
    if (S->max_nodes > 0 && S->nodes >= S->max_nodes) longjmp(S->jb, 1);
    if (S->deadline_ms > 0 && now_ms() >= S->deadline_ms) longjmp(S->jb, 1);
}

static void played(const Search *S, const Tally *t, const uint8_t *board, const Move *m, int mover, Tally *out) {
    const Config *c = S->c;
    int opp = 1 - mover, k;
    *out = *t;
    if (m->to != m->from) {
        int gain = c->adv[mover][m->to] - c->adv[mover][m->from];
        if (c->is_goal[mover][m->to]) {
            gain += c->goal_bonus;
            out->home[mover]++;
        }
        if (c->is_goal[mover][m->from]) {
            gain -= c->goal_bonus;
            out->home[mover]--;
        }
        out->value[mover] += gain;
    }
    for (k = 0; k < m->nj; k++) {
        int sq = m->j[k], piece = board[sq];
        int lost = (IS_KNIGHT(piece) ? c->knight : c->man) + c->adv[opp][sq];
        if (c->is_goal[opp][sq]) {
            lost += c->goal_bonus;
            out->home[opp]--;
        }
        out->value[opp] -= lost;
        out->pieces[opp]--;
    }
}

/* The game's result for `mover` if `t` is a finished position (mirrors Game._decide), else NONE. */
static int result_of(const Config *c, const Tally *t, int mover) {
    int side;
    for (side = 0; side < 2; side++)
        if (t->home[side] >= c->castle_to_win) return side == mover ? WIN : -WIN;
    for (side = 0; side < 2; side++) {
        if (!t->pieces[side]) {
            int winner = 1 - side;
            if (c->wins_need_two && t->pieces[winner] < 2) continue;
            return winner == mover ? WIN : -WIN;
        }
    }
    if (c->draws && t->pieces[mover] <= 1 && t->pieces[1 - mover] <= 1) return 0;
    return NONE;
}

static void apply_move(const Config *c, const uint8_t *from_board, uint8_t *to_board, const Move *m) {
    int k;
    memcpy(to_board, from_board, (size_t)c->size);
    to_board[m->to] = from_board[m->from];
    if (m->to != m->from) to_board[m->from] = 0;
    for (k = 0; k < m->nj; k++) to_board[m->j[k]] = 0;
}

static uint64_t hash_after(uint64_t h, const uint8_t *board, const Move *m) {
    int piece = board[m->from], k;
    if (m->to != m->from) h ^= ZP[piece][m->from] ^ ZP[piece][m->to];
    for (k = 0; k < m->nj; k++) h ^= ZP[board[m->j[k]]][m->j[k]];
    return h;
}

static uint64_t hash_board(const Config *c, const uint8_t *board) {
    uint64_t h = 0;
    int i;
    for (i = 0; i < c->size; i++)
        if (board[i]) h ^= ZP[board[i]][i];
    return h;
}

/* The turns of the position at stack level `lv`, ready to try: scored, with the best-known first. */
static int build_kids(Search *S, int lv, int side, Move *moves, int n, uint32_t first, Kid *kids) {
    const Config *c = S->c;
    int i;
    for (i = 0; i < n; i++) {
        Kid *kd = &kids[i];
        Move *m = &moves[i];
        kd->m = m;
        kd->idx = i;
        kd->mk = move_key(m);
        kd->cm[0] = S->cm[lv][0];
        kd->cm[1] = S->cm[lv][1];
        if (c->is_goal[side][m->from] && c->is_goal[side][m->to]) kd->cm[side]++;
        played(S, &S->tally[lv], S->board[lv], m, side, &kd->after);
        kd->st = kd->after.value[side] - kd->after.value[1 - side];
        kd->order = (int64_t)kd->st + (first && kd->mk == first ? ((int64_t)1 << 40) : 0);
    }
    return n;
}

static int search(Search *S, int lv, int side, int depth, int alpha, int beta, Move *moves, int n);

/* The value for `side` of playing `kd` from the position at level `lv` (depth plies, this one included). */
static int score_child(Search *S, int lv, int side, const Kid *kd, int depth, int alpha, int beta, int ply) {
    const Config *c = S->c;
    int result = result_of(c, &kd->after, side);
    if (result == NONE) {
        int opp = 1 - side, n;
        Move *list;
        if (depth <= 1) return kd->st;
        apply_move(c, S->board[lv], S->board[lv + 1], kd->m);
        S->hash[lv + 1] = hash_after(S->hash[lv], S->board[lv], kd->m);
        S->tally[lv + 1] = kd->after;
        S->cm[lv + 1][0] = kd->cm[0];
        S->cm[lv + 1][1] = kd->cm[1];
        S->expanded++;
        n = gen_moves(c, S->board[lv + 1], opp, kd->cm[opp], level_moves(S, lv + 1),
                      level_moves(S, lv + 1) + MAXMOVES, &list);
        if (n > 0) return -search(S, lv + 1, opp, depth - 1, -beta, -alpha, list, n);
        /* the opponent has no move: blocked, which wins unless that would leave a lone piece */
        if (c->wins_need_two && kd->after.pieces[side] < 2) return 0;
        result = WIN;
    }
    return result > 0 ? result - ply : result < 0 ? result + ply : 0;
}

/* The value of the position at level `lv` for `side` to move, whose legal turns are moves[0..n). */
static int search(Search *S, int lv, int side, int depth, int alpha, int beta, Move *moves, int n) {
    uint64_t key;
    TT *e;
    uint32_t first = 0;
    int original_alpha = alpha, best = -WIN - 1, i, limit;
    uint32_t best_key = 0;
    Kid *kids;

    tick(S);
    key = S->hash[lv] ^ ZSIDE[side] ^ ZCM[0][S->cm[lv][0] < 7 ? S->cm[lv][0] : 7] ^
          ZCM[1][S->cm[lv][1] < 7 ? S->cm[lv][1] : 7];
    e = &S->tt[key & S->ttmask];
    if (e->key == key && e->depth >= 1) {
        first = e->best;
        if (e->depth >= depth) {
            if (e->flag == 0) return e->score;
            if (e->flag == 1) {
                if (e->score > alpha) alpha = e->score;
            } else if (e->score < beta) {
                beta = e->score;
            }
            if (alpha >= beta) return e->score;
        }
    }

    kids = level_kids(S, lv);
    build_kids(S, lv, side, moves, n, first, kids);
    limit = n;
    if (S->beam && depth >= 2 && n > S->beam) limit = S->beam;

    for (i = 0; i < limit; i++) {
        int b = i, j, score;
        Kid tmp;
        for (j = i + 1; j < n; j++)
            if (kids[j].order > kids[b].order) b = j;
        if (b != i) {
            tmp = kids[i];
            kids[i] = kids[b];
            kids[b] = tmp;
        }
        tick(S);
        score = score_child(S, lv, side, &kids[i], depth, alpha, beta, lv + 1);
        if (score > best) {
            best = score;
            best_key = kids[i].mk;
        }
        if (best > alpha) alpha = best;
        if (alpha >= beta) break;
    }

    e = &S->tt[key & S->ttmask];
    e->key = key;
    e->score = best;
    e->best = best_key;
    e->depth = (int16_t)depth;
    e->flag = best <= original_alpha ? 2 : best >= beta ? 1 : 0;
    return best;
}

static int cmp_prev(const void *a, const void *b) {
    const Kid *x = (const Kid *)a, *y = (const Kid *)b;
    if (x->order != y->order) return x->order < y->order ? 1 : -1;
    return x->idx - y->idx;
}

/*
 * Search the given root turns. `root` holds, for each turn: from, to, number of captures, the
 * captured squares. `tally_in` is {white pieces, black pieces, white in enemy castle, black in
 * enemy castle, white value, black value}. Fills out_scores (one per turn: exact for the best
 * turn and any within `slack` of it, an upper bound for the rest) and out_info
 * {depth reached, nodes, expanded}. Returns 0, or negative on a failure.
 */
EXPORT int ai_search(void *cfg, const int32_t *board_in, int side, int cm_w, int cm_b, const int32_t *tally_in,
                     int n_root, const int32_t *root, const int32_t *penalty, int64_t max_ms, int64_t max_nodes,
                     int max_depth, int min_depth, int beam, int slack, int32_t *out_scores, int64_t *out_info) {
    const Config *c = (const Config *)cfg;
    Search *S;
    Move *rootm;
    Kid *rk;
    int32_t *last;
    int i, k, depth, used = 0, ret = 0, failed = 0;
    int64_t start = now_ms();

    if (!c || n_root <= 0 || max_depth >= MAXPLY - 2) return -1;
    S = (Search *)calloc(1, sizeof(Search));
    rootm = (Move *)calloc((size_t)n_root, sizeof(Move));
    rk = (Kid *)calloc((size_t)n_root, sizeof(Kid));
    last = (int32_t *)calloc((size_t)n_root, sizeof(int32_t));
    if (!S || !rootm || !rk || !last) {
        ret = -2;
        goto done;
    }
    S->tt = (TT *)calloc((size_t)1 << TT_BITS, sizeof(TT));
    if (!S->tt) {
        ret = -2;
        goto done;
    }
    S->ttmask = ((uint64_t)1 << TT_BITS) - 1;
    S->c = c;
    S->beam = beam;
    S->max_nodes = max_nodes;
    S->deadline_ms = max_ms > 0 ? start + max_ms : 0;

    for (i = 0; i < c->size; i++) S->board[0][i] = (uint8_t)board_in[i];
    S->hash[0] = hash_board(c, S->board[0]);
    S->tally[0].pieces[0] = tally_in[0];
    S->tally[0].pieces[1] = tally_in[1];
    S->tally[0].home[0] = tally_in[2];
    S->tally[0].home[1] = tally_in[3];
    S->tally[0].value[0] = tally_in[4];
    S->tally[0].value[1] = tally_in[5];
    S->cm[0][0] = cm_w;
    S->cm[0][1] = cm_b;

    for (i = 0; i < n_root; i++) {
        Move *m = &rootm[i];
        m->from = (int16_t)root[used++];
        m->to = (int16_t)root[used++];
        m->nj = (int16_t)root[used++];
        if (m->nj > MAXJ) {
            ret = -3;
            goto done;
        }
        for (k = 0; k < m->nj; k++) m->j[k] = (int16_t)root[used++];
    }
    build_kids(S, 0, side, rootm, n_root, 0, rk);

    for (i = 0; i < n_root; i++) out_scores[i] = 0;
    out_info[0] = out_info[1] = out_info[2] = 0;
    if (n_root == 1) goto done;

    failed = setjmp(S->jb);
    if (failed == 0) {
        for (depth = 1; depth <= max_depth; depth++) {
            int best = -WIN - 1, top;
            S->guaranteed = depth <= min_depth;
            qsort(rk, (size_t)n_root, sizeof(Kid), cmp_prev);
            for (i = 0; i < n_root; i++) {
                Kid *kd = &rk[i];
                int pen = penalty ? penalty[kd->idx] : 0;
                int floor = best - slack - 1 + pen, score;
                if (floor < -WIN - 1) floor = -WIN - 1;
                tick(S);
                score = score_child(S, 0, side, kd, depth, floor, WIN + 1, 1) - pen;
                last[kd->idx] = score;
                if (score > best) best = score;
                kd->order = score; /* provisional: finished only if this depth completes */
            }
            /* this depth finished: keep its scores */
            top = best;
            for (i = 0; i < n_root; i++) out_scores[rk[i].idx] = last[rk[i].idx];
            out_info[0] = depth;
            if (top >= WIN - 100 || top <= -WIN + 100) break;
        }
    }
    if (failed == 2) ret = -2; /* out of memory part way through */
    out_info[1] = S->nodes;
    out_info[2] = S->expanded;

done:
    if (S) {
        for (i = 0; i < MAXPLY; i++) {
            free(S->mlev[i]);
            free(S->klev[i]);
        }
        free(S->tt);
    }
    free(S);
    free(rootm);
    free(rk);
    free(last);
    return ret;
}
