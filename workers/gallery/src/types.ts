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
}

export interface ButtondownClient {
  subscribe(
    apiKey: string,
    email: string,
    tag: string,
  ): Promise<{
    ok: boolean;
    alreadySubscribed: boolean;
    error?: string;
    status?: number;
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
