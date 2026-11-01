export function refusal(input: {status:number;json:Record<string,unknown>}, status:number, code:string):boolean {
  const e=input.json?.error as Record<string,unknown>|undefined;
  return input.status===status && Object.keys(input.json).length===1 && !!e && e.code===code && typeof e.message==="string" && typeof e.request_id==="string" && e.request_id.length>0 && Object.keys(e).sort().join(",")==="code,message,request_id";
}
export function ownedIdentity(items:Array<{id:number;target_role:string}>,own:number,foreign:number,role:string):boolean {
  return own!==foreign && items.length===1 && items[0].id===own && items[0].target_role===role && !items.some(x=>x.id===foreign);
}
