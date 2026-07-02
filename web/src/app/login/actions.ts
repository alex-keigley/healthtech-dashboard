"use server";

import { redirect } from "next/navigation";
import {
  destroySession,
  loginWithPassword,
  requestOtp,
  verifyOtp,
} from "@/lib/auth";

export interface LoginActionState {
  error?: string;
  info?: string;
  otpSent?: boolean;
  email?: string;
}

export async function passwordLoginAction(
  _prevState: LoginActionState,
  formData: FormData
): Promise<LoginActionState> {
  const email = String(formData.get("email") || "").trim();
  const password = String(formData.get("password") || "");
  const next = String(formData.get("next") || "/");

  if (!email || !password) {
    return { error: "Invalid credentials" };
  }

  const ok = await loginWithPassword(email, password);
  if (!ok) {
    return { error: "Invalid credentials" };
  }

  redirect(next || "/");
}

export async function requestOtpAction(
  _prevState: LoginActionState,
  formData: FormData
): Promise<LoginActionState> {
  const email = String(formData.get("email") || "").trim();

  if (!email) {
    return { error: "Enter an email address" };
  }

  // Generic response regardless of whether the account exists.
  await requestOtp(email);

  return {
    otpSent: true,
    email,
    info: "If that email has an account, a sign-in code has been sent.",
  };
}

export async function verifyOtpAction(
  _prevState: LoginActionState,
  formData: FormData
): Promise<LoginActionState> {
  const email = String(formData.get("email") || "").trim();
  const code = String(formData.get("code") || "").trim();
  const next = String(formData.get("next") || "/");

  if (!email || !code) {
    return { error: "Invalid or expired code", otpSent: true, email };
  }

  const ok = await verifyOtp(email, code);
  if (!ok) {
    return { error: "Invalid or expired code", otpSent: true, email };
  }

  redirect(next || "/");
}

export async function signOutAction(): Promise<void> {
  await destroySession();
  redirect("/");
}
