import { describe, expect, it } from "vitest";
import { validRefusal, validView } from "../privacy_request_connected_e2e/assertions";
const view = () => ({public_id:"a".repeat(32), request_type:"correction", type_label:"Correction", status:"submitted", result_category:null, created_at:"2026-01-01", updated_at:null});
describe("privacy-request connected evidence controls", () => {
  it("accepts only the owner projection and submitted state", () => {
    expect(validView(view())).toBe(true);
    expect(validView({...view(), request_note:"synthetic"})).toBe(false);
    expect(validView({...view(), result_category:"correction_made"})).toBe(false);
    expect(validView({...view(), public_id:"bad"})).toBe(false);
    expect(validView(null)).toBe(false);
  });
  it("rejects server failures, incorrect classifications and missing envelopes", () => {
    const valid={status:401,data:{error:{code:"unauthorized",message:"Authentication required",request_id:"r"}}};
    expect(validRefusal(valid,401,"unauthorized")).toBe(true);
    for (const status of [0,200,403,429,500,503]) expect(validRefusal({...valid,status},401,"unauthorized")).toBe(false);
    expect(validRefusal({...valid,data:{error:{code:"other",message:"x",request_id:"r"}}},401,"unauthorized")).toBe(false);
    expect(validRefusal({...valid,data:{error:{code:"unauthorized",message:"x"}}},401,"unauthorized")).toBe(false);
    expect(validRefusal({...valid,data:{...valid.data,items:[]}},401,"unauthorized")).toBe(false);
  });
});
