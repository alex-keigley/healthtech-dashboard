"use client";

import { useActionState, useState } from "react";
import {
  passwordLoginAction,
  requestOtpAction,
  verifyOtpAction,
  type LoginActionState,
} from "./actions";

const initialState: LoginActionState = {};

export default function LoginForm({ next }: { next: string }) {
  const [mode, setMode] = useState<"password" | "otp">("password");

  const [passwordState, passwordFormAction, passwordPending] = useActionState(
    passwordLoginAction,
    initialState
  );
  const [requestState, requestFormAction, requestPending] = useActionState(
    requestOtpAction,
    initialState
  );
  const [verifyState, verifyFormAction, verifyPending] = useActionState(
    verifyOtpAction,
    initialState
  );

  const otpSent = requestState.otpSent || verifyState.otpSent;
  const otpEmail = verifyState.email ?? requestState.email ?? "";

  return (
    <div
      className="rounded-lg border p-6 shadow-sm"
      style={{
        background: "var(--color-surface)",
        borderColor: "var(--color-border)",
        borderRadius: "var(--radius-lg)",
      }}
    >
      <div className="mb-6 flex gap-2 border-b" style={{ borderColor: "var(--color-border)" }}>
        <button
          type="button"
          onClick={() => setMode("password")}
          className="px-3 py-2 text-sm font-medium"
          style={{
            color: mode === "password" ? "var(--color-primary)" : "var(--color-text-muted)",
            borderBottom: mode === "password" ? "2px solid var(--color-primary)" : "2px solid transparent",
          }}
        >
          Password
        </button>
        <button
          type="button"
          onClick={() => setMode("otp")}
          className="px-3 py-2 text-sm font-medium"
          style={{
            color: mode === "otp" ? "var(--color-primary)" : "var(--color-text-muted)",
            borderBottom: mode === "otp" ? "2px solid var(--color-primary)" : "2px solid transparent",
          }}
        >
          Email code
        </button>
      </div>

      {mode === "password" && (
        <form action={passwordFormAction} className="flex flex-col gap-4">
          <input type="hidden" name="next" value={next} />
          <Field label="Email" name="email" type="email" />
          <Field label="Password" name="password" type="password" />
          {passwordState.error && <ErrorText message={passwordState.error} />}
          <SubmitButton pending={passwordPending} label="Sign in" />
        </form>
      )}

      {mode === "otp" && !otpSent && (
        <form action={requestFormAction} className="flex flex-col gap-4">
          <Field label="Email" name="email" type="email" />
          {requestState.error && <ErrorText message={requestState.error} />}
          <SubmitButton pending={requestPending} label="Send code" />
        </form>
      )}

      {mode === "otp" && otpSent && (
        <form action={verifyFormAction} className="flex flex-col gap-4">
          <input type="hidden" name="next" value={next} />
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            If that email has an account, a 6-digit code has been sent. It expires in 10 minutes.
          </p>
          <input type="hidden" name="email" value={otpEmail} />
          <Field label="Email" name="email_display" type="email" defaultValue={otpEmail} disabled />
          <Field label="6-digit code" name="code" type="text" />
          {verifyState.error && <ErrorText message={verifyState.error} />}
          <SubmitButton pending={verifyPending} label="Verify code" />
        </form>
      )}
    </div>
  );
}

function Field({
  label,
  name,
  type,
  defaultValue,
  disabled,
}: {
  label: string;
  name: string;
  type: string;
  defaultValue?: string;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <input
        name={disabled ? undefined : name}
        type={type}
        defaultValue={defaultValue}
        disabled={disabled}
        required={!disabled}
        className="rounded-md border px-3 py-2 text-sm outline-none"
        style={{
          borderColor: "var(--color-border)",
          borderRadius: "var(--radius-md)",
          background: disabled ? "var(--color-bg)" : "var(--color-surface)",
        }}
      />
    </label>
  );
}

function ErrorText({ message }: { message: string }) {
  return (
    <p className="text-sm" style={{ color: "var(--color-danger)" }}>
      {message}
    </p>
  );
}

function SubmitButton({ pending, label }: { pending: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-md px-4 py-2 text-sm font-medium"
      style={{
        background: "var(--color-primary)",
        color: "var(--color-primary-contrast)",
        borderRadius: "var(--radius-md)",
        opacity: pending ? 0.7 : 1,
      }}
    >
      {pending ? "Please wait..." : label}
    </button>
  );
}
