import { C, bg, footer, kicker, panel, subtitle, title, trace } from "./common.mjs";

const stages = [
  ["detect", "equipment.alarm.raised.v1", "trend/raw API + reference flow", "BoI sop-instance"],
  ["analyze", "root_cause.analysis.requested.v1", "raw/guide API + stage analysis", "BoI analysis"],
  ["guide", "maintenance.guide.requested.v1", "guide API + stage analysis", "BoI runbook"],
  ["correct", "corrective_action.requested.v1", "notify + stage analysis + approvals", "BoI action"],
];

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "SOP TIMELINE");
  title(slide, ctx, "The status page follows the SOP stage graph, not a hardcoded event list.", false, 70, 35);
  subtitle(slide, ctx, "The same trace shows four workflow events, four generated BoIs, and the manual handoff set required by the SOP.");

  const startX = 72;
  const y = 250;
  const w = 260;
  for (let i = 0; i < stages.length; i += 1) {
    const x = startX + i * 292;
    panel(slide, ctx, x, y, w, 206, C.white, i === 3 ? C.amber : C.green);
    ctx.addText(slide, { x: x + 18, y: y + 18, width: w - 36, height: 24, text: `${i + 1}. ${stages[i][0]}`, fontSize: 17, bold: true, color: C.ink });
    ctx.addText(slide, { x: x + 18, y: y + 54, width: w - 36, height: 38, text: stages[i][1], fontSize: 12, color: C.blue, typeface: ctx.fonts.mono });
    ctx.addText(slide, { x: x + 18, y: y + 104, width: w - 36, height: 42, text: stages[i][2], fontSize: 13, color: C.body });
    ctx.addText(slide, { x: x + 18, y: y + 158, width: w - 36, height: 24, text: stages[i][3], fontSize: 13, bold: true, color: C.green });
    if (i < stages.length - 1) {
      ctx.addShape(slide, { x: x + w + 14, y: y + 102, width: 36, height: 2, fill: C.rule });
      ctx.addShape(slide, { geometry: "triangle", x: x + w + 46, y: y + 97, width: 12, height: 10, fill: C.rule });
    }
  }

  panel(slide, ctx, 88, 506, 1080, 82, "#F0F6F2", C.green);
  ctx.addText(slide, {
    x: 112,
    y: 526,
    width: 1040,
    height: 30,
    text: `Trace ${trace.id}: ${trace.events} events, ${trace.actions} actions, ${trace.generatedBois} generated BoIs, ${trace.manualHandoffs} manual handoffs.`,
    fontSize: 21,
    bold: true,
    color: C.ink,
  });
  footer(slide, ctx, 3, "Source: workflow-status.json, public SOP workflow metadata");
  return slide;
}
