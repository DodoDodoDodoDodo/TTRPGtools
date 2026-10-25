// The detail side pane (DDB's right-hand sidebar): one entry at a time, opened from any link.
export const pane = $state({ open: false, kind: null, ref: null, extra: null, stack: [] });

export function show(kind, ref, extra = null) {
  if (pane.open) pane.stack.push({ kind: pane.kind, ref: pane.ref, extra: pane.extra });
  pane.kind = kind;
  pane.ref = ref;
  pane.extra = extra;
  pane.open = true;
}

export function back() {
  const prev = pane.stack.pop();
  if (prev) Object.assign(pane, prev);
  else close();
}

export function close() {
  pane.open = false;
  pane.stack = [];
}
