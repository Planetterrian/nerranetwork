/**
 * Minimal Resend transactional-email client.
 *
 * Resend's `POST /emails` takes JSON (`from`, `to`, `subject`, `html`,
 * optional `text`) and an `Authorization: Bearer <RESEND_API_KEY>`
 * header. That's the whole interface we need.
 *
 * The Worker keeps the API key and "from" address as secrets
 * (`RESEND_API_KEY` + `RESEND_FROM_EMAIL`); the operator sets both
 * via `wrangler secret put` once.
 */

const RESEND_ENDPOINT = "https://api.resend.com/emails";


export interface SendEmailParams {
  to: string;
  subject: string;
  html: string;
  text?: string;
}

export interface SendEmailResult {
  ok: boolean;
  id?: string;
  error?: string;
  status?: number;
}

export async function sendEmail(
  apiKey: string,
  fromAddress: string,
  params: SendEmailParams,
): Promise<SendEmailResult> {
  if (!apiKey) return { ok: false, error: "no api key" };
  if (!fromAddress) return { ok: false, error: "no from address" };
  let resp: Response;
  try {
    resp = await fetch(RESEND_ENDPOINT, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        from: fromAddress,
        to: [params.to],
        subject: params.subject,
        html: params.html,
        text: params.text,
      }),
    });
  } catch (e) {
    return { ok: false, error: `RESEND_DOWN: ${(e as Error).message ?? "fetch failed"}` };
  }
  if (resp.status !== 200) {
    return { ok: false, status: resp.status, error: `RESEND_HTTP_${resp.status}` };
  }
  try {
    const body = (await resp.json()) as { id?: string };
    return { ok: true, id: body?.id, status: 200 };
  } catch {
    return { ok: true, status: 200 };
  }
}
