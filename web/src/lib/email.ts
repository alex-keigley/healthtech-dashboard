import nodemailer from "nodemailer";

function buildTransport() {
  const host = process.env.SMTP_HOST;
  if (!host) return null;

  return nodemailer.createTransport({
    host,
    port: Number(process.env.SMTP_PORT) || 587,
    secure: Number(process.env.SMTP_PORT) === 465,
    auth: process.env.SMTP_USER
      ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
      : undefined,
  });
}

async function sendMail(to: string, subject: string, text: string): Promise<void> {
  const transport = buildTransport();
  const from = process.env.SMTP_FROM || "Healthtech Dashboard <no-reply@example.com>";

  if (!transport) {
    // DEV MODE: no SMTP_HOST configured — print instead of sending.
    console.log(
      `\n[DEV MODE] Email not sent (SMTP_HOST unset). Would send to ${to}:\n` +
        `Subject: ${subject}\n${text}\n`
    );
    return;
  }

  await transport.sendMail({ from, to, subject, text });
}

export async function sendOtpEmail(to: string, code: string): Promise<void> {
  await sendMail(
    to,
    "Your Healthtech Dashboard sign-in code",
    `Your one-time sign-in code is: ${code}\n\nThis code expires in 10 minutes. If you didn't request this, you can ignore this email.`
  );
}
