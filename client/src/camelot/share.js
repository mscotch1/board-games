// Sharing the invite link through the device's own share sheet (messages, mail, chat apps...), where the browser has one.

/** Whether this browser can open a share sheet for `data`. */
export function canShare(nav, data) {
  if (typeof nav?.share !== 'function') {
    return false;
  }
  return typeof nav.canShare === 'function' ? Boolean(nav.canShare(data)) : true;
}

/** Opens the share sheet. Resolves 'shared', 'cancelled' (the person closed it) or 'failed'. */
export async function shareInvite(nav, data) {
  try {
    await nav.share(data);
    return 'shared';
  } catch (error) {
    return error?.name === 'AbortError' ? 'cancelled' : 'failed';
  }
}
