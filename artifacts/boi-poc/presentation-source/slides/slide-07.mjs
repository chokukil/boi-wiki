import { C, bg, footer, kicker, metric, node, panel, title } from "./common.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "SSO + RUNTIME READINESS");
  title(slide, ctx, "SK hynix SSO mode now works for UI sessions and automated harness checks.", false, 70, 35);

  node(slide, ctx, 76, 210, 250, 116, "Keycloak dev realm", "users 100001/100002/100003\nOIDC PKCE + token validation", C.blue);
  node(slide, ctx, 384, 210, 250, 116, "Mock HCP", "team/role permission merge\nviewer/editor/promoter gates", C.blue);
  node(slide, ctx, 692, 210, 250, 116, "BoI API", "SSO auth + service-token delegation\nsource/draft/workflow gates", C.green);
  node(slide, ctx, 1000, 210, 190, 116, "Langflow", "hynix SSO image\nBoI API service token", C.green);

  panel(slide, ctx, 82, 406, 1094, 118, C.white, C.rule);
  metric(slide, ctx, 118, 430, 160, "4/4", "health endpoints ok", C.green);
  metric(slide, ctx, 338, 430, 170, "127", "pytest cases passed", C.blue);
  metric(slide, ctx, 568, 430, 190, "0", "failed E2E actions", C.green);
  metric(slide, ctx, 818, 430, 220, "2", "Langflow flows imported", C.blue);

  ctx.addText(slide, {
    x: 82,
    y: 564,
    width: 1088,
    height: 36,
    text: "Recent commits: d708745 SSO auth model, aa1f280 Langflow-hynix runtime integration, 2796031 SSO smoke auth support.",
    fontSize: 14,
    color: C.muted,
    typeface: ctx.fonts.mono,
  });
  footer(slide, ctx, 7, "Source: runtime-health.txt, pytest output, git log");
  return slide;
}
