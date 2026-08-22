/**
 * Entry point for the Nerra Network gallery Worker.
 *
 * Routes:
 *
 *   POST /api/subscribe   - email gate enrolment
 *   GET  /api/login       - request a magic-link email
 *   GET  /api/magic       - consume a magic-link token
 *   GET  /api/download    - stream a private R2 object
 *   GET  /api/health      - liveness ping (no auth)
 *
 * Everything else falls through to 404.
 */

import * as buttondown from "./buttondown";
import { corsHeaders, handlePreflight, jsonResponse } from "./cors";
import {
  handleDownload,
  handleLogin,
  handleMagic,
  handleSubscribe,
} from "./handlers";
import {
  handleAccount,
  handleAdminSpecs,
  handlePersonalFeed,
  handlePreferences,
  handleStripeWebhook,
} from "./personal";
import * as resend from "./resend";
import type { Env, HandlerDeps } from "./types";

const DEPS: HandlerDeps = { buttondown, resend };

// /api/feed/<token>/<file> — the one wildcard route (private feeds).
const FEED_PATH_RE = /^\/api\/feed\/([a-f0-9]{16,64})\/([A-Za-z0-9_.-]+)$/;


export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return handlePreflight(request);
    }
    const url = new URL(request.url);
    const route = `${request.method} ${url.pathname}`;
    try {
      const feedMatch = request.method === "GET"
        ? url.pathname.match(FEED_PATH_RE)
        : null;
      if (feedMatch) {
        return await handlePersonalFeed(
          request, env, feedMatch[1], feedMatch[2]);
      }
      switch (route) {
        case "POST /api/subscribe":
          return await handleSubscribe(request, env, DEPS);
        case "GET /api/login":
          return await handleLogin(request, env, DEPS);
        case "GET /api/magic":
          return await handleMagic(request, env, DEPS);
        case "GET /api/download":
          return await handleDownload(request, env, DEPS);
        case "GET /api/account":
          return await handleAccount(request, env);
        case "POST /api/account/preferences":
          return await handlePreferences(request, env);
        case "POST /api/stripe/webhook":
          return await handleStripeWebhook(request, env);
        case "GET /api/admin/personal-specs":
          return await handleAdminSpecs(request, env);
        case "GET /api/health":
          return jsonResponse(request, 200, { ok: true });
        default:
          return jsonResponse(request, 404, { ok: false, error: "not found" });
      }
    } catch (e) {
      console.error("unhandled error", route, (e as Error).message);
      return jsonResponse(request, 500, {
        ok: false,
        error: "internal error",
      });
    }
  },
};
