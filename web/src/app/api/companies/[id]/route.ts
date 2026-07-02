import { NextResponse } from "next/server";
import { getCompanyDetail } from "@/lib/queries/public";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const parsedId = parseInt(id, 10);

  if (Number.isNaN(parsedId)) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const detail = getCompanyDetail(parsedId);

  if (!detail) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  return NextResponse.json(detail);
}
