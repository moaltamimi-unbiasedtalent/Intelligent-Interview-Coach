import { describe, expect, it } from "vitest";
import { ownedIdentity, refusal } from "../history_identity_connected_e2e/assertions";
describe("History connected evidence controls",()=>{
 it("rejects wrong, foreign or duplicate record identities",()=>{
  expect(ownedIdentity([{id:10,target_role:"owner"}],10,20,"owner")).toBe(true);
  expect(ownedIdentity([{id:20,target_role:"owner"}],10,20,"owner")).toBe(false);
  expect(ownedIdentity([{id:10,target_role:"wrong"}],10,20,"owner")).toBe(false);
  expect(ownedIdentity([{id:10,target_role:"owner"},{id:10,target_role:"owner"}],10,20,"owner")).toBe(false);
 });
 it("rejects service failures, wrong classifications and leaked fields",()=>{
  const x={status:404,json:{error:{code:"not_found",message:"missing",request_id:"synthetic"}}};
  expect(refusal(x,404,"not_found")).toBe(true);
  expect(refusal({...x,status:500},404,"not_found")).toBe(false);
  expect(refusal({...x,status:503},404,"not_found")).toBe(false);
  expect(refusal({...x,json:{...x.json,interview:{}}},404,"not_found")).toBe(false);
  expect(refusal({...x,json:{error:{...x.json.error,code:"history_not_available"}}},404,"not_found")).toBe(false);
 });
});
