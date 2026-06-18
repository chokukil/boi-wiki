import { C, bg, footer, kicker, tableRow, title } from "./common.mjs";

const docs = [
  ["detect", "equipment.alarm.raised.v1", "boi:private:100001:20260619014404:99a3d5", "evt-20260619014403-7fd0ff"],
  ["analyze", "root_cause.analysis.requested.v1", "boi:private:100001:20260619014411:b0876e", "evt-20260619014411-6e5dca"],
  ["guide", "maintenance.guide.requested.v1", "boi:private:100001:20260619014424:bc81ac", "evt-20260619014424-d998a8"],
  ["correct", "corrective_action.requested.v1", "boi:private:100001:20260619014436:7ff90d", "evt-20260619014435-304677"],
];

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "BOI MATERIALIZATION");
  title(slide, ctx, "Generated BoIs are stage-specific execution records, not reused PoC boilerplate.", false, 70, 35);

  tableRow(slide, ctx, 190, ["Stage", "Event Type", "Generated BoI", "Event ID"], {
    header: true,
    widths: [140, 300, 460, 260],
    x: 60,
    height: 44,
  });
  docs.forEach((row, idx) => tableRow(slide, ctx, 238 + idx * 62, row, {
    widths: [140, 300, 460, 260],
    x: 60,
    height: 62,
  }));

  ctx.addShape(slide, { x: 82, y: 532, width: 1110, height: 58, fill: "#F0F6F2", line: ctx.line(C.green, 1) });
  ctx.addText(slide, {
    x: 108,
    y: 548,
    width: 1060,
    height: 30,
    text: "Smoke asserts generated docs have no 'AI Native Workflow Interpretation' boilerplate and no pending enrichment.",
    fontSize: 18,
    bold: true,
    color: C.ink,
  });
  footer(slide, ctx, 5, "Source: workflow-status.json, generated-boi.html, run_equipment_sop_poc.log");
  return slide;
}
