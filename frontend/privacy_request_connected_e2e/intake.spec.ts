import { validRefusal, validView } from "./assertions";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";

const api = process.env.STORY_API_URL!;
const accounts = JSON.parse(readFileSync(process.env.STORY_ACCOUNTS_FILE!, "utf8")) as Record<string, {id:number; email:string}>;
const password = "Synthetic-Story-Test-Password-42";
const notes = ["SYNTHETIC correction alpha", "SYNTHETIC correction beta"];
function check(value: unknown, label: string): asserts value { if (!value) throw new Error(label); }
async function context(browser: Browser) {
  const ctx = await browser.newContext();
  await ctx.route("**/*", route => ["localhost", "127.0.0.1"].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort("blockedbyclient"));
  return ctx;
}
async function call(page: Page, path: string, method = "GET", body?: object) {
  return page.evaluate(async ({api, path, method, body}) => {
    const r = await fetch(api + path, {method, credentials:"include", headers: body ? {"content-type":"application/json"} : undefined, body: body ? JSON.stringify(body) : undefined});
    return {status:r.status, data:await r.json()};
  }, {api, path, method, body});
}
async function login(page: Page, email: string) {
  await page.goto("/sign-in"); await page.locator("#email").fill(email); await page.locator("#password").fill(password);
  await page.getByRole("button", {name:/sign in/i}).click();
  await expect.poll(async () => (await call(page, "/auth/me")).status).toBe(200);
}
test("correction intake persists and remains owner scoped", async ({browser}) => {
  const owner = await context(browser), other = await context(browser), anon = await context(browser);
  const observations: Record<string, boolean | number> = {};
  try {
    const pages = [await owner.newPage(), await other.newPage()];
    await login(pages[0], accounts.owner.email); await login(pages[1], accounts.other.email);
    const refs: string[] = []; let posts = 0;
    for (let i=0;i<2;i++) {
      const p=pages[i]; await p.goto("/account/data");
      await expect(p.getByText("We cannot promise a response time.")).toBeVisible();
      await expect(p.getByText(/needs a person to look at it/i)).toBeVisible();
      const panel=p.getByTestId("dp-privacy-requests");
      await panel.getByLabel("What is your request about?").selectOption("correction");
      await panel.getByLabel("Details (optional)").fill(notes[i]);
      p.on("request", req => { if (new URL(req.url()).pathname === "/api/v1/privacy/requests" && req.method() === "POST") posts++; });
      const response=p.waitForResponse(r => new URL(r.url()).pathname === "/api/v1/privacy/requests" && r.request().method() === "POST");
      await panel.getByRole("button", {name:"Send request"}).click();
      const r=await response; check(r.status()===201,"create status"); const item=await r.json(); check(validView(item),"candidate projection and state"); refs.push(item.public_id);
      await expect(panel.getByRole("form", {name:"Privacy requests"}).getByRole("status")).toContainText(item.public_id);
      await expect(panel.locator("ul").getByText(item.public_id, {exact:false})).toBeVisible();
    }
    check(posts===2 && refs[0]!==refs[1],"single creation per account");
    for(let i=0;i<2;i++) {
      const list=await call(pages[i],"/privacy/requests"); check(list.status===200 && list.data.total===1 && list.data.items.length===1,"owner list count");
      check(validView(list.data.items[0]),"candidate projection and state"); check(list.data.items[0].public_id===refs[i] && list.data.items[0].public_id!==refs[1-i],"reciprocal isolation");
      const panel=pages[i].getByTestId("dp-privacy-requests"); await expect(panel.locator("ul").getByText(refs[i],{exact:false})).toBeVisible();
      check(await panel.locator("ul").getByText(refs[1-i],{exact:false}).count()===0,"foreign UI exclusion");
      await pages[i].reload(); await expect(panel.locator("ul").getByText(refs[i],{exact:false})).toBeVisible(); await expect(panel.locator("ul").getByText("Submitted", {exact:true})).toBeVisible();
    }
    const guest=await anon.newPage(); await guest.goto("/sign-in");
    const denials=[await call(guest,"/privacy/requests"), await call(guest,"/privacy/requests","POST",{request_type:"correction"}),
      await call(pages[0],"/privacy/requests","POST",{request_type:"correction",user_id:accounts.other.id}),
      await call(pages[0],"/privacy/requests","POST",{request_type:"invalid_type"}),
      await call(pages[0],"/privacy/requests","POST",{request_type:"correction",note:"x".repeat(1001)}),
      await call(pages[1],`/admin/privacy/requests/${refs[0]}/status`,"POST",{status:"acknowledged"})];
    for(const [i,d] of denials.entries()) { check(validRefusal(d,[401,401,422,422,422,403][i],["unauthorized","unauthorized","invalid_request","http_error","http_error","forbidden"][i]),"denial contract "+i); }
    for(let i=0;i<2;i++) {
      const fresh=await context(browser);
      try { const p=await fresh.newPage(); await login(p,i === 0 ? accounts.owner.email : accounts.other.email); await p.goto("/account/data"); await expect(p.getByTestId("dp-privacy-requests").locator("ul").getByText(refs[i],{exact:false})).toBeVisible(); const l=await call(p,"/privacy/requests"); check(l.status===200 && l.data.total===1 && l.data.items[0].public_id===refs[i] && l.data.items[0].status==="submitted","fresh session persistence"); } finally { await fresh.close(); }
    }
    for(let i=0;i<2;i++){ const l=await call(pages[i],"/privacy/requests"); check(l.status===200 && l.data.total===1 && l.data.items[0].public_id===refs[i] && l.data.items[0].status==="submitted","unchanged requests"); }
    observations.submissions=2; observations.owner_isolation=true; observations.reload=true; observations.fresh_session=true; observations.refusals=6; observations.unchanged=true;
    writeFileSync(join(process.env.STORY_OUTPUT_DIR!,"privacy-facts.json"),JSON.stringify(observations),{mode:0o600});
  } finally { await owner.close(); await other.close(); await anon.close(); }
});

// Synthetic control: list loading may expose another status outside the form.
test("acknowledgement reference remains scoped to the request form", async ({page}) => {
  const ref = "a".repeat(32);
  await page.setContent(`<div data-testid="dp-privacy-requests"><form aria-label="Privacy requests"><p role="status">Your request was recorded. Reference: ${ref}</p></form><div role="status">Loading</div></div>`);
  const panel = page.getByTestId("dp-privacy-requests");
  const formStatus = panel.getByRole("form", {name:"Privacy requests"}).getByRole("status");
  await expect(panel.getByRole("status")).toHaveCount(2);
  await expect(formStatus).toHaveCount(1);
  await expect(formStatus).toContainText(ref);
  await expect(formStatus).not.toContainText("b".repeat(32));
  await page.locator("form [role=status]").evaluate(node => node.remove());
  await expect(formStatus).toHaveCount(0);
});
