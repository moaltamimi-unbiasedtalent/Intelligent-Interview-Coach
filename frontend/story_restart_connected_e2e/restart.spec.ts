import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";
const api=process.env.STORY_API_URL!, state=process.env.RESTART_STATE_DIR!;
const accounts=JSON.parse(readFileSync(process.env.STORY_ACCOUNTS_FILE!,"utf8")) as Record<string,{id:number;email:string}>;
const password="Synthetic-Story-Test-Password-42";
function check(v:unknown, label:string): asserts v {if(!v) throw new Error(label);}
async function context(browser:Browser) { const ctx=await browser.newContext(); await ctx.route("**/*", route => ["localhost","127.0.0.1"].includes(new URL(route.request().url()).hostname) ? route.continue():route.abort("blockedbyclient")); return ctx; }
async function request(page:Page,path:string,method="GET",body?:object) { return page.evaluate(async ({api,path,method,body})=>{const r=await fetch(api+path,{method,credentials:"include",headers:body?{"Content-Type":"application/json"}:undefined,body:body?JSON.stringify(body):undefined}); return {status:r.status,json:await r.json()};},{api,path,method,body}); }
async function login(page:Page,email:string){await page.goto("/sign-in"); await page.locator("#email").fill(email); await page.locator("#password").fill(password); await page.getByRole("button",{name:/sign in/i}).click(); await expect.poll(async()=> (await request(page,"/auth/me")).status).toBe(200);}
function foreignDenial(x:{status:number;json:Record<string,unknown>}) { const e=x.json?.error as Record<string,unknown> | undefined; return x.status===404 && Object.keys(x.json).length===1 && !!e && e.code==="not_found" && e.message==="Story not found." && typeof e.request_id==="string" && e.request_id.length>0 && Object.keys(e).sort().join(",")==="code,message,request_id"; }
const expected={title:"Synthetic restart story",situation:"Synthetic situation",task:"Synthetic task",action:"Synthetic action",result:"Synthetic edited result",status:"user_created",verification:"unverified"};
function matches(x:Record<string,unknown>, id:number, opp:number){return x.id===id && x.opportunity_id===opp && Object.entries(expected).every(([k,v])=>x[k]===v);}
test("owned story and isolation across API process replacement",async({browser})=>{
 const ca=await context(browser), cb=await context(browser);
 try {const a=await ca.newPage(),b=await cb.newPage(); await login(a,accounts.owner.email); await login(b,accounts.other.email);
  if(process.env.RESTART_PHASE==="before"){
   const opp=await request(a,"/opportunities","POST",{target_role:"Synthetic role",company_name:"Synthetic employer"});check(opp.status===201,"opportunity create"); const oppId=opp.json.id as number;
   await a.goto("/documents"); await a.getByRole("button",{name:"New story"}).click();
   for(const [label,value] of Object.entries({Title:expected.title,Situation:expected.situation,Task:expected.task,Action:expected.action,Result:"Synthetic original result"})) await a.getByLabel(label).fill(value);
   await a.locator("form").getByLabel("Opportunity").selectOption(String(oppId));
   const cr=a.waitForResponse(r=>new URL(r.url()).pathname==="/api/v1/stories"&&r.request().method()==="POST");await a.getByRole("button",{name:"Save",exact:true}).click();const created=await cr;check(created.status()===201,"story create");const id=(await created.json()).id as number;
   const card=a.getByTestId(`story-${id}`);await expect(card).toContainText("Written by you");await expect(card).toContainText("No supporting source"); await card.getByRole("button",{name:"Edit",exact:true}).click();await a.getByLabel("Result").fill(expected.result);
   const ur=a.waitForResponse(r=>new URL(r.url()).pathname===`/api/v1/stories/${id}`&&r.request().method()==="PATCH");await a.getByRole("button",{name:"Save",exact:true}).click();check((await ur).status()===200,"story edit");
   const own=await request(a,`/stories/${id}`);check(own.status===200&&matches(own.json,id,oppId),"before story fields");
   const other=await request(b,"/stories","POST",{title:"Synthetic other story",status:"user_created"});check(other.status===201,"positive control create");const otherId=other.json.id as number;check((await request(b,`/stories/${otherId}`)).status===200,"positive control read");
   const suggestions=await request(a,"/stories/suggest","POST",{terms:[],opportunity_id:oppId});check(suggestions.status===200&&suggestions.json.suggestions.some((x:{id:number;requires_approval:boolean})=>x.id===id&&x.requires_approval),"suggestion approval");
   const denied=await request(a,"/interviews","POST",{configuration:{target_role:"Synthetic role",industry_or_sector:"technology",career_level:"senior",number_of_questions:2,story_ids:[id]}});check(denied.status===422,"missing story consent");check((await request(a,`/stories/${id}`)).json.use_count===0,"no unapproved use");
   writeFileSync(join(state,"restart-private.json"),JSON.stringify({id,oppId,otherId}),{mode:0o600});
  } else {
   const {id,oppId,otherId}=JSON.parse(readFileSync(join(state,"restart-private.json"),"utf8")); await a.goto("/documents");const card=a.getByTestId(`story-${id}`);await expect(card).toHaveCount(1);await expect(card).toContainText(expected.result);await expect(card).toContainText("Written by you");await expect(card).toContainText("No supporting source");
   const before=await request(a,`/stories/${id}`);check(before.status===200&&matches(before.json,id,oppId),"after story fields");
   const ownList=await request(a,"/stories");check(ownList.status===200&&ownList.json.stories.filter((x:{id:number})=>x.id===id).length===1,"owner list once");
   const own=await request(b,`/stories/${otherId}`);check(own.status===200&&own.json.id===otherId,"other positive control");
   const list=await request(b,"/stories");check(list.status===200&&!list.json.stories.some((x:{id:number})=>x.id===id),"foreign list exclusion");
   const read=await request(b,`/stories/${id}`),edit=await request(b,`/stories/${id}`,"PATCH",{title:"Unauthorized change"});
   check(foreignDenial(read)&&foreignDenial(edit),"foreign denial contract");
   const after=await request(a,`/stories/${id}`);check(after.status===200&&matches(after.json,id,oppId),"foreign attempts unchanged");
   writeFileSync(join(state,"after-facts.json"),JSON.stringify({owner:true,other:true,isolation:true,foreign_read:404,foreign_edit:404,unchanged:true}),{mode:0o600});
  }
 } finally {await ca.close();await cb.close();}
});
