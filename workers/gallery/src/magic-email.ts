/**
 * HTML email body for the magic-link login flow.
 *
 * The copy is account-centric, not gallery-centric. Under the
 * one-identity model (Aug 2026) this single link signs a person into
 * everything: the newsletter, member perks, gallery downloads, and the
 * paid personal feed. It used to say "sign in and download
 * full-resolution images", which meant somebody paying $4.99/mo to
 * manage their daily show received an email about downloading pictures.
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
  /** Oct 29 2026: the six-digit code for the installed app (an emailed
   *  link opens in the browser, which on iPhone is not the app). */
  code?: string;
}): MagicLinkEmail {
  const subject = "Sign in to your Nerra Network account";
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
          <h1 style="margin:0 0 8px;font-size:1.25rem;color:#ffffff;">Your Nerra Network account</h1>
          <p style="margin:0;color:#8b8fae;font-size:0.95rem;">Click the button below to sign in. Your account covers your personal daily feed, your newsletter settings, member perks and gallery downloads.</p>
        </td></tr>
        <tr><td align="center" style="padding:24px 28px;">
          <a href="${safeUrl}"
             style="display:inline-block;padding:12px 28px;background:#6B47FF;color:#ffffff;font-weight:600;text-decoration:none;border-radius:10px;font-size:0.95rem;">Sign in</a>
        </td></tr>
        ${opts.code ? `<tr><td align="center" style="padding:0 28px 20px;color:#8b8fae;font-size:0.9rem;">
          <p style="margin:0 0 8px;">Using the Nerra app on your Home Screen? Type this code there instead:</p>
          <p style="margin:0;font-size:1.8rem;font-weight:700;letter-spacing:0.28em;color:#ffffff;font-family:ui-monospace,Menlo,monospace;">${escapeHtml(opts.code.slice(0, 3) + " " + opts.code.slice(3))}</p>
        </td></tr>` : ""}
        <tr><td style="padding:0 28px 24px;color:#8b8fae;font-size:0.8rem;line-height:1.5;">
          <p style="margin:0 0 8px;">The link${opts.code ? " and the code expire" : " expires"} in ${ttl} minutes. If you didn&rsquo;t request this email you can safely ignore it &mdash; nobody will be signed in unless they click the button above.</p>
          <p style="margin:0;word-break:break-all;">If the button doesn&rsquo;t work, paste this URL into your browser:<br><span style="color:#cbd5e0;">${safeUrl}</span></p>
        </td></tr>
      </table>
      <p style="margin:18px 0 0;color:#64748b;font-size:0.75rem;">Nerra Network &middot; <a href="https://nerranetwork.com" style="color:#64748b;">nerranetwork.com</a></p>
    </td></tr>
  </table>
</body>
</html>`;
  const text =
    `Sign in to your Nerra Network account\n\n` +
    `Click the link below to sign in. Your account covers your personal ` +
    `daily feed, your newsletter settings, member perks and gallery ` +
    `downloads:\n\n` +
    `${opts.magicUrl}\n\n` +
    (opts.code ? `Using the Nerra app on your Home Screen? Type this code there instead: ${opts.code}\n\n` : "") +
    `The link expires in ${ttl} minutes. If you didn't request this email ` +
    `you can safely ignore it.\n\n` +
    `— Nerra Network (https://nerranetwork.com)\n`;
  return { subject, html, text };
}

/**
 * Oct 28 2026: the email a new member gets the moment Stripe confirms the
 * checkout. Until now the webhook wrote the member record and sent
 * nothing, and sign-in only mailed addresses on the newsletter list — a
 * buyer who paid straight from the join page was told "check your inbox"
 * and never heard from us. This carries a sign-in link (longer-lived than
 * a login link: it waits in an inbox), the private feed URL, and how to
 * add it to the three apps most people use.
 */
export function buildWelcomeEmail(opts: {
  firstName: string;
  feedUrl: string;
  signInUrl: string;
  signInHours: number;
  firstEditionNow: boolean;
}): MagicLinkEmail {
  const subject = "Your Nerra Personal feed is ready";
  const hello = opts.firstName ? `Welcome, ${opts.firstName}` : "Welcome";
  const feed = escapeHtml(opts.feedUrl);
  const signIn = escapeHtml(opts.signInUrl);
  // Oct 28 2026: one tap into the member's own podcast app. The add page
  // reads the feed token from the URL fragment (never sent to a server) and
  // offers each app's own subscribe link; on a computer it shows a code to
  // scan with the phone.
  const tokenMatch = /\/api\/feed\/([0-9a-f]{32})\/feed\.rss$/.exec(opts.feedUrl);
  const addUrl = tokenMatch ? `https://nerranetwork.com/add.html#${tokenMatch[1]}` : "";
  const addButton = addUrl
    ? `<tr><td align="center" style="padding:18px 28px 0;">
          <a href="${escapeHtml(addUrl)}"
             style="display:inline-block;padding:12px 28px;background:#ffffff;color:#0b0f1a;font-weight:700;text-decoration:none;border-radius:999px;font-size:0.95rem;">Add to my podcast app</a>
          <p style="margin:8px 0 0;color:#8b8fae;font-size:0.8rem;">Open this on your phone: one tap for Apple Podcasts, Overcast, Pocket Casts, Castro, AntennaPod or Podcast Addict.</p>
        </td></tr>`
    : "";
  const when = opts.firstEditionNow
    ? "Your first edition is being made now and appears in your feed within a few minutes."
    : "Your first edition arrives with the next morning's build.";
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escapeHtml(subject)}</title>
</head>
<body style="margin:0;padding:0;background:#0b0f1a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e8ecf4;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0f1a;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:520px;background:#111627;border:1px solid rgba(255,255,255,0.08);border-radius:14px;">
        <tr><td style="padding:28px 28px 8px;">
          <h1 style="margin:0 0 8px;font-size:1.25rem;color:#ffffff;">${escapeHtml(hello)} to Nerra Personal</h1>
          <p style="margin:0;color:#c3c8d8;font-size:0.95rem;line-height:1.55;">${escapeHtml(when)} Mira opens each edition by name and plays your shows in the order you chose.</p>
        </td></tr>
        ${addButton}
        <tr><td style="padding:18px 28px 4px;">
          <p style="margin:0 0 6px;color:#ffffff;font-weight:600;font-size:0.95rem;">Your private feed</p>
          <p style="margin:0;word-break:break-all;color:#cbd5e0;font-size:0.85rem;background:#0b0f1a;border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:10px;">${feed}</p>
          <p style="margin:10px 0 0;color:#8b8fae;font-size:0.85rem;line-height:1.55;">Apple Podcasts: Library, then the &hellip; menu, then <em>Follow a Show by URL</em>. Overcast: the + button, then <em>Add URL</em>. Pocket Casts: Search, then paste the URL. The link is yours alone; please don&rsquo;t share it.</p>
        </td></tr>
        <tr><td align="center" style="padding:22px 28px;">
          <a href="${signIn}"
             style="display:inline-block;padding:12px 28px;background:#6B47FF;color:#ffffff;font-weight:600;text-decoration:none;border-radius:10px;font-size:0.95rem;">Pick your shows</a>
        </td></tr>
        <tr><td style="padding:0 28px 24px;color:#8b8fae;font-size:0.8rem;line-height:1.5;">
          <p style="margin:0;">The button signs you in to your account page, where you choose your shows and their order. It works for ${opts.signInHours} hours; after that, ask for a new sign-in link on the account page.</p>
        </td></tr>
      </table>
      <p style="margin:18px 0 0;color:#64748b;font-size:0.75rem;">Nerra Network &middot; <a href="https://nerranetwork.com" style="color:#64748b;">nerranetwork.com</a></p>
    </td></tr>
  </table>
</body>
</html>`;
  const text =
    `${hello} to Nerra Personal\n\n` +
    `${when}\n\n` +
    (addUrl ? `Add it to your podcast app in one tap (open on your phone):\n${addUrl}\n\n` : "") +
    `Your private feed (yours alone; please don't share it):\n${opts.feedUrl}\n\n` +
    `Apple Podcasts: Library > ... > Follow a Show by URL. Overcast: + > Add URL. ` +
    `Pocket Casts: Search, then paste the URL.\n\n` +
    `Pick your shows (signs you in, works for ${opts.signInHours} hours):\n${opts.signInUrl}\n\n` +
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
