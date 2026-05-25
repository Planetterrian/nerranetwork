/**
 * HTML email body for the magic-link login flow.
 *
 * Kept deliberately plain — single CTA, brand colour from the
 * existing design tokens, no images (Buttondown / Outlook will
 * sometimes block remote images on first send to a new sender).
 * Includes a plain-text alternative for clients that prefer it.
 */

export interface MagicLinkEmail {
  subject: string;
  html: string;
  text: string;
}

export function buildMagicLinkEmail(opts: {
  magicUrl: string;
  ttlMinutes: number;
}): MagicLinkEmail {
  const subject = "Sign in to the Nerra Network gallery";
  const safeUrl = escapeHtml(opts.magicUrl);
  const ttl = opts.ttlMinutes;
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escapeHtml(subject)}</title>
</head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e8ecf4;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0f1a;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:480px;background:#111627;border:1px solid rgba(255,255,255,0.08);border-radius:14px;">
        <tr><td style="padding:28px 28px 8px;">
          <h1 style="margin:0 0 8px;font-size:1.25rem;color:#ffffff;">Nerra Network gallery</h1>
          <p style="margin:0;color:#8b8fae;font-size:0.95rem;">Click the button below to sign in and download full-resolution images.</p>
        </td></tr>
        <tr><td align="center" style="padding:24px 28px;">
          <a href="${safeUrl}"
             style="display:inline-block;padding:12px 28px;background:#6B47FF;color:#ffffff;font-weight:600;text-decoration:none;border-radius:10px;font-size:0.95rem;">Sign in</a>
        </td></tr>
        <tr><td style="padding:0 28px 24px;color:#8b8fae;font-size:0.8rem;line-height:1.5;">
          <p style="margin:0 0 8px;">The link expires in ${ttl} minutes. If you didn&rsquo;t request this email you can safely ignore it &mdash; nobody will be signed in unless they click the button above.</p>
          <p style="margin:0;word-break:break-all;">If the button doesn&rsquo;t work, paste this URL into your browser:<br><span style="color:#cbd5e0;">${safeUrl}</span></p>
        </td></tr>
      </table>
      <p style="margin:18px 0 0;color:#64748b;font-size:0.75rem;">Nerra Network &middot; <a href="https://nerranetwork.com" style="color:#64748b;">nerranetwork.com</a></p>
    </td></tr>
  </table>
</body>
</html>`;
  const text =
    `Sign in to the Nerra Network gallery\n\n` +
    `Click the link below to sign in and download full-resolution images:\n\n` +
    `${opts.magicUrl}\n\n` +
    `The link expires in ${ttl} minutes. If you didn't request this email ` +
    `you can safely ignore it.\n\n` +
    `— Nerra Network (https://nerranetwork.com)\n`;
  return { subject, html, text };
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
