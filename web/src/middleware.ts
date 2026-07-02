import { NextRequest, NextResponse } from "next/server";

// Lightweight gate: presence of the session cookie only. Real role checks
// (reviewer vs admin) happen in layouts/actions via requireRole(), since
// that needs a DB lookup that Edge middleware shouldn't do on every request.
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const guarded = pathname.startsWith("/review") || pathname.startsWith("/admin");

  if (guarded && !request.cookies.get("session")) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/review/:path*", "/admin/:path*"],
};
