// A simulated room for the interview scenario (Oct 22 2026).
//
// Loads voximplant/scenarios/age_of_ai_interview.js into a node vm with the
// VoxEngine and Grok globals stubbed and timers under the test's control,
// then drives one named scenario through the room's own functions and
// prints what the room did as JSON. Used by tests/test_room_holds_2026_10_22.py.
// No network, no audio: this checks the room's DECISIONS, not the voice API.
"use strict";
const fs = require("fs");
const vm = require("vm");

const [, , scenarioPath, which] = process.argv;
const source = fs.readFileSync(scenarioPath, "utf8");

// --- controllable clock and timers ---------------------------------------
let now = Date.UTC(2026, 9, 22, 16, 30, 0);
let timerSeq = 0;
const timers = new Map();
function fakeSetTimeout(fn, ms) {
  const id = ++timerSeq;
  timers.set(id, { at: now + Math.max(0, ms || 0), fn });
  return id;
}
function fakeClearTimeout(id) { timers.delete(id); }
function advance(ms) {
  const until = now + ms;
  for (;;) {
    let next = null;
    for (const [id, t] of timers) if (t.at <= until && (!next || t.at < next[1].at)) next = [id, t];
    if (!next) break;
    timers.delete(next[0]);
    now = next[1].at;
    next[1].fn();
  }
  now = until;
}
class FakeDate extends Date {
  constructor(...a) { if (a.length) super(...a); else super(now); }
  static now() { return now; }
}

// --- stub platform ---------------------------------------------------------
const trace = [];
const notes = [];
const events = [];   // responseCreate / responseCancel / clearMediaBuffer
const instructions = [];   // per-response instructions sent with responseCreate
const agent = {
  conversationItemCreate(item) { notes.push(item.item.content[0].text); },
  responseCreate(body) {
    events.push("create");
    instructions.push((body && body.response && body.response.instructions) || "");
  },
  responseCancel() { events.push("cancel"); },
  clearMediaBuffer() { events.push("clear"); },
  addEventListener() {},
  sessionUpdate() {},
};
const ctx = {
  console, JSON, Math, Object, Array, String, Number, Boolean, RegExp, Promise, Error,
  parseInt, parseFloat, isFinite, encodeURIComponent,
  Date: FakeDate,
  setTimeout: fakeSetTimeout, clearTimeout: fakeClearTimeout,
  setInterval: function () { return 0; }, clearInterval: function () {},
  Logger: { write(line) { const m = /\] trace ([^:]+)(?:: (.*))?$/.exec(line); if (m) trace.push({ e: m[1], d: m[2] || "" }); } },
  require() {}, Modules: {},
  VoxEngine: { addEventListener() {}, terminate() {}, customData() { return "{}"; } },
  AppEvents: {}, CallEvents: {}, PlayerEvents: {}, RecorderEvents: {}, ConferenceEvents: {},
  Grok: { VoiceAgentAPIEvents: {} },
  Net: { httpRequestAsync() { return Promise.resolve({ code: 200, text: "{}" }); } },
};
vm.createContext(ctx);
vm.runInContext(source, ctx, { filename: "age_of_ai_interview.js" });
const run = (code) => vm.runInContext(code, ctx);

// A room that has opened, with Mira bridged and a guest in it.
ctx.__agent = agent;
run(`
  runId = "sim"; config = { planned_minutes: 45, show_question: "the one bet you are making" };
  grokAgent = __agent; openingFired = true; sessionReady = true;
  firstJoinAt = Date.now() - 35 * 60 * 1000;
  legs = [{ id: "guest-1", role: "guest", call: {}, joinedAt: firstJoinAt }];
`);

// --- the room's inputs, as the voice API delivers them ---------------------
function guestSays(text, ms) {
  run("inboundSpeaking = true; inboundSpokeAt = Date.now(); noteInboundStart();");
  advance(ms || 2000);
  run("inboundSpeaking = false; noteSpeechEnded(" + (ms || 2000) + ");");   // what SpeechStopped does
  if (text !== null) { ctx.__text = text; run("remember('Guest', __text);"); }
  run("scheduleTurnDecision(TURN_DECIDE_MS);");
}
// The live room: the voice API sends no transcription of the guest, so the
// room hears that they spoke and for how long, never what they said.
function guestSpeaks(ms) { guestSays(null, ms); }
// Grok Voice 3.0: the transcription of one item arrives about every second
// while they talk, each copy the whole item so far, then once more at the end.
let liveItem = 0;
function guestSaysLive(text, ms) {
  const id = "item-" + (++liveItem);
  const words = text.split(" ");
  const steps = Math.max(1, Math.floor((ms || 3000) / 1000));
  run("inboundSpeaking = true; inboundSpokeAt = Date.now(); noteInboundStart();");
  for (let i = 1; i <= steps; i++) {
    advance(1000);
    ctx.__id = id; ctx.__text = words.slice(0, Math.ceil(words.length * i / steps)).join(" ");
    run("noteGuestTranscript(__id, __text);");
  }
  run("inboundSpeaking = false; noteSpeechEnded(" + (steps * 1000) + ");");
  ctx.__id = id; ctx.__text = text;
  run("noteGuestTranscript(__id, __text); noteGuestTranscript(__id, __text);");
  run("scheduleTurnDecision(TURN_DECIDE_MS);");
}
// Run the clock until the room's next hold check-in fires.
function untilCheckIn() {
  const seen = trace.filter(function (x) { return x.e === "hold" && /^check-in /.test(x.d); }).length;
  for (let i = 0; i < 400; i++) {
    advance(1000);
    if (trace.filter(function (x) { return x.e === "hold" && /^check-in /.test(x.d); }).length > seen) return;
  }
  throw new Error("no check-in within 400 s");
}
function serverStartsATurn() { run("markTurnStarted(grokAgent);"); }
function roomTurnStarts() { run("markTurnStarted(grokAgent);"); }   // after a requestTurn
function miraFinishes(text) {
  ctx.__text = text;
  run("miraSpeaking = false; remember('Mira', __text); armDeadAir();");   // what ResponseDone does
}
// A line as 3.0 delivers it: the transcript is done (and generation with it)
// long before the guest has heard the end of the audio.
function miraFinishesLine(text) {
  ctx.__text = text;
  run("noteMiraLineSpoken(__text); miraSpeaking = false; remember('Mira', __text); armDeadAir();");
}
function words(n) { return Array.from({ length: n }, function (_, i) { return "word" + i; }).join(" ") + "?"; }
function state() {
  return run(`({ roundActive, roundIndex, roundAwaitingAnswer, roundClosed, holdMode,
    serverTurnsRerouted, pendingTurn, miraSpeaking, holdResumeOwed, guestAskedToStop })`);
}

const out = {};
if (which === "server_turns_advance_the_round") {
  run("closingPermitted = true; startRound('test', -1);");
  roomTurnStarts();
  miraFinishes("What is the one bet you are making for the next five years?");
  guestSays("My bet is that small teams will run on agents within three years.", 4000);
  // The server ignores create_response:false and starts her reply itself,
  // before the room's own decision fires.
  serverStartsATurn();
  out.afterServerTurn = { events: events.slice(), state: state() };
  advance(5000);
  out.afterDecision = { events: events.slice(), state: state() };
} else if (which === "hold_mode") {
  run("closingPermitted = true; startRound('test', -1);");
  roomTurnStarts();
  miraFinishes("What is the one bet you are making for the next five years?");
  events.length = 0;
  guestSays("Oh, sorry, I have to take this call, give me a moment.", 2500);
  out.entered = state();
  advance(3000);
  guestSays("Hi, yes, the delivery can come on Thursday after two.", 3000);
  serverStartsATurn();
  advance(5000);
  guestSays("Okay, thanks, bye now.", 1500);
  advance(5000);
  out.whileAway = { events: events.slice(), state: state() };
  ctx.__time = "x"; run("startTimeChecks();");   // interval is a no-op stub; the scheduled note must hold
  advance(4 * 60 * 1000);
  out.checkIn = { events: events.slice(), notes: notes.slice(-3), instructions: instructions.slice(-1)[0] };
  roomTurnStarts();
  miraFinishes("I'm still here whenever you're ready.");
  events.length = 0;
  guestSays("Sorry about that, where were we?", 1500);
  out.back = state();
  advance(5000);
  out.afterBack = { events: events.slice(), state: state(), notes: notes.slice(-2), instructions: instructions.slice(-1)[0] };
} else if (which === "hold_ends_on_speech") {
  // The Oct 22 candidate rehearsal: no guest words ever arrive. The hold
  // starts on her line and must end on the guest's speech after a check-in.
  run("closingPermitted = true; startRound('test', -1);");
  roomTurnStarts();
  miraFinishes("What is the one bet you are making for the next five years?");
  guestSpeaks(2500);
  advance(5000);                    // no words arrive; the room waits once, then answered 1/8, asks 2/8
  roomTurnStarts();
  miraFinishes("Of course, take the call, I'll wait.");
  out.entered = state();
  events.length = 0;
  for (let i = 0; i < 6; i++) { guestSpeaks(3000); advance(4000); }
  out.whileAway = { events: events.slice(), state: state() };
  // Three check-ins she says (each one short line), none answered: the
  // guest is still talking to the caller, but never inside a reply window.
  for (let i = 0; i < 3; i++) {
    untilCheckIn();
    roomTurnStarts();
    miraFinishes("I'm still here whenever you're ready.");
    advance(60 * 1000);
    guestSpeaks(3000);
  }
  out.stillHeld = state().holdMode;
  // The fourth: they answer it. Speech, no words.
  untilCheckIn();
  roomTurnStarts();
  advance(3000);
  miraFinishes("I'm still here whenever you're ready.");
  events.length = 0;
  advance(4000);
  guestSpeaks(1500);
  out.back = state();
  advance(5000);
  out.afterBack = { events: events.slice(), state: state(), notes: notes.slice(-2) };
  // She asks the question in play again; the answer (no words) moves the round on.
  roomTurnStarts();
  miraFinishes("Welcome back. So, a book you would recommend?");
  guestSpeaks(4000);
  advance(5000);
  out.afterAnswer = state();
  out.checkIns = trace.filter(function (x) { return x.e === "hold" && /^check-in /.test(x.d); }).length;
} else if (which === "hold_ignores_a_cough") {
  run("closingPermitted = true; startRound('test', -1);");
  roomTurnStarts();
  miraFinishes("Of course, I'll wait.");
  untilCheckIn();
  roomTurnStarts();
  miraFinishes("I'm still here whenever you're ready.");
  guestSpeaks(400);                 // a cough
  out.afterCough = state().holdMode;
  advance(60 * 1000);
  guestSpeaks(3000);                // talking to the caller, outside the reply window
  out.afterLateSpeech = state().holdMode;
} else if (which === "dead_air") {
  // The Oct 22 candidate rehearsal: after her line nobody spoke again. The
  // room breaks the silence twice, then waits for someone to speak.
  roomTurnStarts();
  miraFinishes("So tell me how you first came to the work.");
  events.length = 0;
  advance(19 * 1000);
  out.before = events.slice();
  advance(2000);
  out.first = events.slice();
  roomTurnStarts();
  miraFinishes("How did you start?");
  advance(21 * 1000);
  roomTurnStarts();
  miraFinishes("Where did it begin for you?");
  events.length = 0;
  advance(60 * 1000);
  out.afterMax = events.slice();
  // Speech resets the count: a fresh silence gets its nudges again.
  guestSpeaks(3000);
  advance(5000);
  roomTurnStarts();
  miraFinishes("That's a lovely start. What came next?");
  events.length = 0;
  advance(21 * 1000);
  out.afterReset = events.slice();
  out.nudges = run("deadAirNudgesTotal");
} else if (which === "dead_air_empty_room") {
  // The Oct 22 candidate rehearsal: the guest's leg dropped and she nudged
  // the empty room twice during the rejoin grace.
  roomTurnStarts();
  miraFinishes("Do you still have it?");
  run(`legs = []; scheduleTeardown();`);
  events.length = 0;
  advance(40 * 1000);
  out.events = events.slice();
  out.nudges = run("deadAirNudgesTotal");
} else if (which === "long_line_dead_air") {
  // Oct 22 2026 candidate rehearsal: a 60-word line plays for ~24 s after it
  // has been generated; the silence starts when she stops being heard.
  roomTurnStarts();
  miraFinishesLine(words(60));
  events.length = 0;
  advance(30 * 1000);
  out.during = events.slice();
  advance(20 * 1000);
  out.after = events.slice();
  out.nudges = run("deadAirNudgesTotal");
} else if (which === "turn_waits_for_her_audio") {
  // The room asks for a turn while her last line is still playing: it waits.
  roomTurnStarts();
  miraFinishesLine(words(60));
  events.length = 0;
  advance(1000);
  run("requestTurn(grokAgent);");
  out.immediately = events.slice();
  out.pending = run("pendingTurn");
  advance(25 * 1000);
  out.after = events.slice();
} else if (which === "pause_inside_her_line") {
  // A pause the room hears while her own line still plays is not the guest's.
  roomTurnStarts();
  miraFinishesLine(words(60));
  events.length = 0;
  guestSays("Mm.", 600);
  run("miraAudibleUntil = Date.now() + 10000;");
  advance(1500);
  out.immediately = events.slice();
} else if (which === "cleared_audio_is_silent") {
  roomTurnStarts();
  miraFinishesLine(words(60));
  out.before = run("miraAudible()");
  run("miraSilenced();");
  out.after = run("miraAudible()");
} else if (which === "dead_air_waits_for_a_thinker") {
  // A guest who starts talking inside the twenty seconds is never nudged.
  roomTurnStarts();
  miraFinishes("What was the hardest year?");
  events.length = 0;
  advance(15 * 1000);
  guestSpeaks(6000);
  advance(30 * 1000);
  out.events = events.slice();
  out.nudges = run("deadAirNudgesTotal");
} else if (which === "live_transcription") {
  // The words arrive as 3.0 sends them: one line per item, however many copies.
  roomTurnStarts();
  miraFinishes("What did the first year teach you?");
  const before = run("transcript.length");
  guestSaysLive("It taught me that the customers were never the problem and the dashboards were.", 5000);
  out.lines = run("transcript.length") - before;
  out.lastLine = run("transcript[transcript.length - 1]");
  advance(3000);
  out.answered = state();
  roomTurnStarts();
  miraFinishes("And the second year?");
  guestSaysLive("Sorry, I have to take this call, give me a moment.", 3000);
  out.held = state().holdMode;
  advance(4000);
  guestSaysLive("Hi, yes, Thursday works, after two is fine.", 4000);
  out.stillHeld = state().holdMode;
  guestSaysLive("Sorry about that, where were we?", 3000);
  out.back = state().holdMode;
  guestSaysLive("Actually I'm so sorry, I have to go now, something has come up.", 4000);
  out.stop = state().guestAskedToStop;
  out.traceHasNoWords = !JSON.stringify(trace).match(/Thursday|dashboards|something has come up/);
} else if (which === "sign_off_waits_for_the_round") {
  run("closingPermitted = true; startRound('test', -1);");
  roomTurnStarts();
  events.length = 0;
  run("catchEarlyCloseOnDelta('Thank you so much, that is it, that\\'s the end of the recording');");
  out.inRound = { events: events.slice(), state: state() };
  events.length = 0;
  run("miraSpeaking = true; responseCancelledEarly = false; lastRescueAt = 0;");
  run("guestAskedToStop = true;");
  run("catchEarlyCloseOnDelta('Thank you, that\\'s the end of the recording');");
  out.afterGuestAsked = { events: events.slice() };
  events.length = 0;
  run("guestAskedToStop = false; roundClosed = true; miraSpeaking = true; responseCancelledEarly = false;");
  run("catchEarlyCloseOnDelta('Thank you, that\\'s the end of the recording');");
  out.afterRoundClosed = { events: events.slice() };
} else if (which === "guest_stop_is_heard") {
  run("closingPermitted = true;");
  guestSays("I'm so sorry, I have to go, I've got another meeting.", 2000);
  out.state = state();
} else if (which === "phrases") {
  // Which of the room's phrase rules each line trips (JSON list on stdin-free env).
  const lines = JSON.parse(process.env.ROOM_SIM_PHRASES || "[]");
  ctx.__lines = lines;
  out.phrases = run(`__lines.map(function (t) { return {
    text: t, enter: HOLD_ENTER_RE.test(t), mira_wait: MIRA_HOLD_RE.test(t),
    exit: HOLD_EXIT_RE.test(t), stop: GUEST_STOP_RE.test(t), sign_off: SIGN_OFF_RE.test(t) }; })`);
} else {
  throw new Error("unknown scenario " + which);
}
out.trace = trace;
process.stdout.write(JSON.stringify(out));
