/**
 * Worker env + dependency types.
 *
 * `Env` matches the bindings declared in wrangler.toml. The R2
 * binding is typed via the `@cloudflare/workers-types` global
 * `R2Bucket`. Secrets are plain strings.
 *
 * `HandlerDeps` decouples handlers from the real Buttondown / Resend
 * modules so tests can supply fakes.
 */

export interface Env {
  GALLERY_BUCKET: R2Bucket;
  JWT_SECRET: string;
  BUTTONDOWN_API_KEY: string;
  RESEND_API_KEY: string;
  RESEND_FROM_EMAIL: string;

  // KV binding for rate limiting, revocation, AND (Aug 2026) member
  // accounts — one namespace, prefix-separated (rl:/revoke:/member:/
  // feedtok:/sub:). Every consumer degrades gracefully when absent.
  RATE_LIMIT_KV?: KVNamespace;

  // --- Nerra Personal (Aug 2026) — all optional until provisioned; the
  // personal endpoints answer 503 "not configured" without them.
  PERSONAL_BUCKET?: R2Bucket;          // bucket: nerra-personal
  STRIPE_WEBHOOK_SECRET?: string;      // wrangler secret put
  PERSONAL_ADMIN_TOKEN?: string;       // wrangler secret put (batch builder)
  MEMBER_BOOK_CODE?: string;           // member perks: book discount code

  // --- Plan switching (Sep 2026). A restricted Stripe key (billing
  // portal sessions: write; subscriptions: read) so the account page can
  // open the customer portal, and the two price ids so
  // customer.subscription.updated can map a portal plan switch back to a
  // tier. All optional: without them /api/account/portal answers 503 and
  // the webhook logs and ignores subscription updates.
  STRIPE_SECRET_KEY?: string;          // wrangler secret put
  STRIPE_PRICE_PERSONAL?: string;      // price_… for Personal ($4.99)
  STRIPE_PRICE_PNN?: string;           // price_… for Personal News Network ($8.99)
}

export interface ButtondownClient {
  subscribe(
    apiKey: string,
    email: string,
    // A single tag (the gallery gate) or the resolved list + source tags
    // a funnel landing page sends. See resolveSubscribeTags in handlers.ts.
    tag: string | string[],
  ): Promise<{
    ok: boolean;
    alreadySubscribed: boolean;
    error?: string;
    status?: number;
    /** Redacted upstream body for the Worker log only (see
     *  buttondown.ts SubscribeResult) — never returned to the client. */
    detail?: string;
  }>;
  isSubscribed(
    apiKey: string,
    email: string,
  ): Promise<{
    ok: boolean;
    exists: boolean;
    error?: string;
    status?: number;
  }>;
}

export interface ResendClient {
  sendEmail(
    apiKey: string,
    fromAddress: string,
    params: { to: string; subject: string; html: string; text?: string },
  ): Promise<{ ok: boolean; id?: string; error?: string; status?: number }>;
}

export interface HandlerDeps {
  buttondown: ButtondownClient;
  resend: ResendClient;
}
