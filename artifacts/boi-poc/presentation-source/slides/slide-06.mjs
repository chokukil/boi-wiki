import { C, bg, footer, kicker, node, panel, title } from "./common.mjs";

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "GOVERNANCE");
  title(slide, ctx, "Automation stops at approval boundaries instead of hiding high-risk action state.", false, 70, 35);

  node(slide, ctx, 86, 220, 260, 120, "Action Gateway", "dispatches catalog actions with risk and approval policy", C.blue);
  node(slide, ctx, 488, 158, 300, 110, "Process Hold", "sop.equipment.block_process_progress\nstatus: approval_required", C.amber);
  node(slide, ctx, 488, 316, 300, 110, "Spec / Rule Change", "sop.equipment.change_spec_rule\nstatus: approval_required", C.amber);
  node(slide, ctx, 932, 238, 250, 130, "Manual approval", "manual.equipment.approve_process_hold\nmanual.equipment.approve_spec_rule_change", C.amber);

  ctx.addShape(slide, { x: 346, y: 278, width: 120, height: 2, fill: C.rule });
  ctx.addShape(slide, { geometry: "triangle", x: 460, y: 273, width: 12, height: 10, fill: C.rule });
  ctx.addShape(slide, { x: 788, y: 214, width: 120, height: 2, fill: C.rule });
  ctx.addShape(slide, { geometry: "triangle", x: 902, y: 209, width: 12, height: 10, fill: C.rule });
  ctx.addShape(slide, { x: 788, y: 372, width: 120, height: 2, fill: C.rule });
  ctx.addShape(slide, { geometry: "triangle", x: 902, y: 367, width: 12, height: 10, fill: C.rule });

  panel(slide, ctx, 92, 502, 1060, 76, "#FFF6E8", C.amber);
  ctx.addText(slide, {
    x: 118,
    y: 522,
    width: 1010,
    height: 34,
    text: "The PoC proves control behavior: high-risk system actions are logged and surfaced as approval_required, while manual tasks remain traceable handoffs.",
    fontSize: 19,
    bold: true,
    color: C.ink,
  });
  footer(slide, ctx, 6, "Source: workflow-status.json approval_required_actions");
  return slide;
}
