// ARC-AGI-3 grid palette + render constants — extracted VERBATIM from the official replay
// viewer (arcprize.org/replay/<session_id>, webpack chunk 6072) so our agent's frames render
// pixel-identically to the canonical interface. Value 0..15 -> fill colour; a parallel map gives
// the legible text colour to overlay on each cell; terminal states flash the whole board.

window.ARC = window.ARC || {};

// cell value -> fill colour (the board palette)
window.ARC.CELL_COLORS = {
  0: "#FFFFFF", 1: "#CCCCCC", 2: "#999999", 3: "#666666", 4: "#333333", 5: "#000000",
  6: "#E53AA3", 7: "#FF7BCC", 8: "#F93C31", 9: "#1E93FF", 10: "#88D8F1", 11: "#FFDC00",
  12: "#FF851B", 13: "#921231", 14: "#4FCC30", 15: "#A356D6",
};

// cell value -> contrasting text colour (for the optional value overlay)
window.ARC.TEXT_COLORS = {
  0: "#111111", 1: "#111111", 2: "#ffffff", 3: "#ffffff", 4: "#ffffff", 5: "#ffffff",
  6: "#ffffff", 7: "#ffffff", 8: "#ffffff", 9: "#ffffff", 10: "#111111", 11: "#111111",
  12: "#ffffff", 13: "#ffffff", 14: "#111111", 15: "#ffffff",
};

// full-board flash on a terminal frame (the replay viewer does the same)
window.ARC.STATE_FLASH = { GAME_OVER: "#F93C31", WIN: "#4FCC30" };

// human-readable names, for the legend
window.ARC.COLOR_NAMES = {
  0: "white", 1: "grey-1", 2: "grey-2", 3: "grey-3", 4: "grey-4", 5: "black",
  6: "magenta", 7: "pink", 8: "red", 9: "blue", 10: "cyan", 11: "yellow",
  12: "orange", 13: "maroon", 14: "green", 15: "purple",
};
