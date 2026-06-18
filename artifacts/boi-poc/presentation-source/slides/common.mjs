export const C = {
  ink: "#10151F",
  paper: "#F7F8F5",
  white: "#FFFFFF",
  body: "#263241",
  muted: "#657083",
  rule: "#D8DEE8",
  green: "#1F8A70",
  blue: "#2F6FED",
  amber: "#C47A00",
  red: "#C93636",
};

export const trace = {
  id: "trace-609660cf137c4946aaa833c891f704b7",
  workflow: "equipment-anomaly",
  events: 24,
  actions: 21,
  generatedBois: 4,
  manualHandoffs: 5,
  failed: 0,
};

export function bg(slide, ctx, color = C.paper) {
  ctx.addShape(slide, { x: 0, y: 0, width: 1280, height: 720, fill: color });
}

export function footer(slide, ctx, n, source = "Source: outputs/manual-20260619/e2e-evidence") {
  ctx.addText(slide, {
    x: 56,
    y: 682,
    width: 980,
    height: 18,
    text: source,
    fontSize: 10,
    color: C.muted,
  });
  ctx.addText(slide, {
    x: 1180,
    y: 682,
    width: 44,
    height: 18,
    text: String(n).padStart(2, "0"),
    fontSize: 10,
    color: C.muted,
    align: "right",
  });
}

export function kicker(slide, ctx, text, dark = false) {
  ctx.addShape(slide, {
    name: "kicker-marker",
    x: 56,
    y: 45,
    width: 24,
    height: 3,
    fill: dark ? C.green : C.blue,
  });
  ctx.addText(slide, {
    name: "kicker-label",
    x: 88,
    y: 36,
    width: 520,
    height: 22,
    text,
    fontSize: 12,
    bold: true,
    color: dark ? "#BFD9D1" : C.muted,
    valign: "middle",
  });
}

export function title(slide, ctx, text, dark = false, y = 72, size = 40) {
  ctx.addText(slide, {
    x: 56,
    y,
    width: 980,
    height: 96,
    text,
    fontSize: size,
    bold: true,
    color: dark ? C.white : C.ink,
    typeface: ctx.fonts.title,
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function subtitle(slide, ctx, text, dark = false, y = 154) {
  ctx.addText(slide, {
    x: 58,
    y,
    width: 900,
    height: 52,
    text,
    fontSize: 19,
    color: dark ? "#C8D1DE" : C.body,
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function metric(slide, ctx, x, y, w, value, label, color = C.green, dark = false) {
  ctx.addText(slide, {
    x,
    y,
    width: w,
    height: 44,
    text: value,
    fontSize: 34,
    bold: true,
    color,
    typeface: ctx.fonts.title,
  });
  ctx.addText(slide, {
    x,
    y: y + 46,
    width: w,
    height: 38,
    text: label,
    fontSize: 13,
    color: dark ? "#C8D1DE" : C.muted,
  });
}

export function panel(slide, ctx, x, y, w, h, fill = C.white, line = C.rule) {
  return ctx.addShape(slide, {
    x,
    y,
    width: w,
    height: h,
    fill,
    line: ctx.line(line, 1),
  });
}

export function node(slide, ctx, x, y, w, h, label, caption, color = C.blue) {
  panel(slide, ctx, x, y, w, h, C.white, color);
  ctx.addText(slide, {
    x: x + 16,
    y: y + 14,
    width: w - 32,
    height: 24,
    text: label,
    fontSize: 16,
    bold: true,
    color: C.ink,
  });
  ctx.addText(slide, {
    x: x + 16,
    y: y + 44,
    width: w - 32,
    height: h - 54,
    text: caption,
    fontSize: 12,
    color: C.body,
  });
}

export function connector(slide, ctx, x1, y1, x2, y2, color = C.rule) {
  ctx.addShape(slide, {
    x: x1,
    y: y1,
    width: x2 - x1,
    height: 2,
    fill: color,
  });
  ctx.addShape(slide, {
    geometry: "triangle",
    x: x2 - 6,
    y: y2 - 5,
    width: 12,
    height: 10,
    fill: color,
  });
}

export function tableRow(slide, ctx, y, cols, opts = {}) {
  const { x = 70, widths = [250, 210, 250, 360], height = 42, header = false } = opts;
  let cx = x;
  for (let i = 0; i < cols.length; i += 1) {
    ctx.addShape(slide, {
      x: cx,
      y,
      width: widths[i],
      height,
      fill: header ? "#EBF0F6" : C.white,
      line: ctx.line(C.rule, 1),
    });
    ctx.addText(slide, {
      x: cx + 10,
      y: y + 8,
      width: widths[i] - 20,
      height: height - 12,
      text: cols[i],
      fontSize: header ? 12 : 11,
      bold: header,
      color: header ? C.ink : C.body,
    });
    cx += widths[i];
  }
}
