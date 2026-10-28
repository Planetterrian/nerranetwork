// The studio's headset-following code (age-of-ai-studio.html section 4c,
// Oct 28 2026) run in a node vm against a fake device list, so the tests can
// say what the page does when someone puts on headphones mid-setup or
// mid-call. Prints JSON. Used by tests/test_studio_devices_2026_10_28.py.
"use strict";
const fs = require("fs");
const vm = require("vm");
const [, , htmlPath, which] = process.argv;
const html = fs.readFileSync(htmlPath, "utf8");
const a = html.indexOf("  // ---- 4c. Follow the headset");
const b = html.indexOf("  // ---- 4d. Background blur");
if (a < 0 || b < 0) throw new Error("section 4c not found");
const code = html.slice(a, b);

function el(id) {
  const e = { id, _value: "", innerHTML: "", textContent: "", options: [], selectedIndex: 0,
           classList: { _h: true, add() { this._h = true; }, remove() { this._h = false; },
                        contains() { return this._h; } },
           addEventListener() {} };
  // As a real <select>: the value picks the option.
  Object.defineProperty(e, "value", {
    get() { return this._value; },
    set(v) { this._value = v; const i = this.options.findIndex(function (o) { return o.value === v; }); if (i >= 0) this.selectedIndex = i; },
  });
  return e;
}
const els = {};
["micSel", "micSelCall", "deviceNote", "deviceNoteCall", "micCheckMsg"].forEach(function (id) { els[id] = el(id); });
const log = [];
let devices = [];
let deviceListener = null;
const ctx = {
  console, JSON, Math, Object, Array, String, Number, Boolean, RegExp, Promise, Error,
  setTimeout: function (fn) { fn(); return 1; }, clearTimeout: function () {},
  document: { getElementById: function (id) { return els[id] || null; } },
  navigator: { mediaDevices: {
    enumerateDevices: function () { return Promise.resolve(devices.slice()); },
    addEventListener: function (ev, fn) { if (ev === "devicechange") deviceListener = fn; },
  } },
  VoxImplant: { Hardware: { AudioDeviceManager: { get: function () { return {
    getDefaultAudioSettings: function () { return {}; },
    setDefaultAudioSettings: function (s) { log.push({ default_audio: s }); },
    getCallAudioSettings: function () { return {}; },
    setCallAudioSettings: function (c, s) { log.push({ call_audio: s }); return Promise.resolve(); },
  }; } } } },
  activeCall: null, localStream: { id: "s" }, micAccess: true, micOk: true, micVerdict: "pass",
  switchDevices: function (what) { log.push({ switchDevices: what, mic: els.micSel.value }); },
  switchCallMic: function (id) { log.push({ switchCallMic: id }); },
  setMicMsg: function (t) { els.micCheckMsg.textContent = t; },
  fillCallMics: function () { els.micSelCall.options = els.micSel.options.slice(); els.micSelCall.value = els.micSel.value; },
};
// listDevices / hasOption as the page has them (section 2), on the fake DOM.
ctx.hasOption = function (sel, value) { return sel.options.some(function (o) { return o.value === value; }); };
vm.createContext(ctx);
vm.runInContext(code, ctx);
ctx.listDevices = function (known) {
  const devs = known || devices;
  const mic = els.micSel, keep = mic.value;
  mic.options = devs.filter(function (d) { return d.kind === "audioinput"; })
    .map(function (d) { return { value: d.deviceId, textContent: d.label }; });
  if (keep && ctx.hasOption(mic, keep)) mic.value = keep;
  else mic.value = mic.options.length ? mic.options[0].value : "";
  if (!ctx.knownInputs) { vm.runInContext("rememberDevices(__devs); suggestBetterMic(__devs);", Object.assign(ctx, { __devs: devs })); }
  if (ctx.activeCall) ctx.fillCallMics();
  return Promise.resolve(devs);
};
const run = (c) => vm.runInContext(c, ctx);

const BUILTIN = { kind: "audioinput", deviceId: "builtin", label: "MacBook Pro Microphone (Built-in)" };
const DEF_BUILTIN = { kind: "audioinput", deviceId: "default", label: "Default - MacBook Pro Microphone (Built-in)" };
const SPEAKERS = { kind: "audiooutput", deviceId: "spk", label: "MacBook Pro Speakers (Built-in)" };
const AIRPODS_IN = { kind: "audioinput", deviceId: "airpods-in", label: "Patrick's AirPods Pro" };
const AIRPODS_OUT = { kind: "audiooutput", deviceId: "airpods-out", label: "Patrick's AirPods Pro" };
const DEF_AIRPODS = { kind: "audioinput", deviceId: "default", label: "Default - Patrick's AirPods Pro" };
const USB_IN = { kind: "audioinput", deviceId: "usb-in", label: "Jabra Evolve2 30 USB (0b0e:3061)" };
const WIRED_IN = { kind: "audioinput", deviceId: "wired-in", label: "External Microphone" };

async function settle() { for (let i = 0; i < 10; i++) await Promise.resolve(); await new Promise(function (r) { setImmediate(r); }); }
async function connect(next) { devices = next; deviceListener(); await settle(); }
function state() {
  return { mic: els.micSel.value, callMic: els.micSelCall.value, note: els.deviceNote.innerHTML,
           noteCall: els.deviceNoteCall.innerHTML, micMsg: els.micCheckMsg.textContent, log: log.slice() };
}

(async function () {
  const out = {};
  devices = [DEF_BUILTIN, BUILTIN, SPEAKERS];
  await ctx.listDevices();
  if (which === "airpods_in_setup") {
    await connect([DEF_AIRPODS, BUILTIN, AIRPODS_IN, SPEAKERS, AIRPODS_OUT]);
    out.after = state();
  } else if (which === "airpods_in_call") {
    ctx.activeCall = { id: "call" };
    ctx.fillCallMics();
    await connect([DEF_AIRPODS, BUILTIN, AIRPODS_IN, SPEAKERS, AIRPODS_OUT]);
    out.after = state();
    // One click takes the AirPods' microphone anyway.
    out.button = /useBtMic/.test(els.deviceNoteCall.innerHTML);
  } else if (which === "usb_in_call") {
    ctx.activeCall = { id: "call" };
    ctx.fillCallMics();
    await connect([DEF_BUILTIN, BUILTIN, USB_IN, SPEAKERS]);
    out.after = state();
  } else if (which === "wired_in_setup") {
    await connect([DEF_BUILTIN, BUILTIN, WIRED_IN, SPEAKERS]);
    out.after = state();
  } else if (which === "unplugged") {
    await connect([DEF_BUILTIN, BUILTIN, USB_IN, SPEAKERS]);
    log.length = 0;
    await connect([DEF_BUILTIN, BUILTIN, SPEAKERS]);
    out.after = state();
  } else if (which === "airpods_already_on") {
    ctx.knownInputs = null;
    devices = [DEF_AIRPODS, BUILTIN, AIRPODS_IN, AIRPODS_OUT];
    els.micSel.value = "";
    await ctx.listDevices();
    out.after = state();
  } else {
    throw new Error("unknown " + which);
  }
  process.stdout.write(JSON.stringify(out));
})().catch(function (e) { console.error(e); process.exit(1); });
