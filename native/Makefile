# Builds the computer player's search library. Needs a C compiler and make:
#
#   make -C native            # writes native/libaisearch.so
#
# The server works without it (it falls back to a slower search written in Python).
CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -std=c99

libaisearch.so: aisearch.c
	$(CC) $(CFLAGS) -fvisibility=hidden -shared -fPIC -o $@ aisearch.c

clean:
	rm -f libaisearch.so

.PHONY: clean
