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
import * as resend from "./resend";
import type { Env, HandlerDeps } from "./types";

const DEPS: HandlerDeps = { buttondown, resend };


export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return handlePreflight(request);
    }
    const url = new URL(request.url);
    const route = `${request.method} ${url.pathname}`;
    try {
      switch (route) {
        case "POST /api/subscribe":
          return await handleSubscribe(request, env, DEPS);
        case "GET /api/login":
          return await handleLogin(request, env, DEPS);
        case "GET /api/magic":
          return await handleMagic(request, env, DEPS);
        case "GET /api/download":
          return await handleDownload(request, env, DEPS);
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
