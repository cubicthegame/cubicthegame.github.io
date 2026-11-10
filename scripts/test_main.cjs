const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Exercise the actual page script without relying on a preview's media support.
function page({ reduced = false, saveData = false, observer = true, rejectPlay = false } = {}) {
  const events = new Map();
  const motion = { matches: reduced, addEventListener: (_, callback) => { motion.change = callback; } };
  const menu = {
    open: false,
    focused: false,
    querySelector: () => ({ focus: () => { menu.focused = true; } }),
    contains: target => target === menu,
  };
  const videos = [0, 1].map(index => ({
    dataset: {},
    source: { dataset: { src: `/assets/webm/video-${index}.webm` }, src: '' },
    loads: 0, plays: 0, pauses: 0,
    querySelectorAll() { return [this.source]; },
    load() { this.loads++; },
    play() { this.plays++; return rejectPlay ? Promise.reject(new Error('Autoplay blocked')) : Promise.resolve(); },
    pause() { this.pauses++; },
  }));
  const document = {
    hidden: false,
    querySelector: selector => selector === '.mobile-nav' ? menu : null,
    querySelectorAll: selector => selector === '.lazy-video' ? videos : [],
    addEventListener: (name, callback) => events.set(name, callback),
  };
  let intersection;
  const window = { scrollY: 0, addEventListener() {}, matchMedia: () => motion };
  const context = { window, document, navigator: { connection: { saveData } } };
  if (observer) {
    context.IntersectionObserver = class {
      constructor(callback) { intersection = callback; }
      observe() {}
    };
    window.IntersectionObserver = context.IntersectionObserver;
  }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/js/main.js'), 'utf8'), context);
  return { videos, menu, document, motion, events,
    enter: (index, visible = true) => intersection([{ target: videos[index], isIntersecting: visible }]) };
}

test('videos download only near the screen, load once, and pause offscreen', () => {
  const p = page();
  assert.ok(p.videos.every(video => !video.source.src && video.loads === 0));
  p.enter(0);
  assert.equal(p.videos[0].source.src, '/assets/webm/video-0.webm');
  assert.equal(p.videos[0].loads, 1);
  assert.equal(p.videos[0].plays, 1);
  assert.equal(p.videos[1].source.src, '');
  p.enter(0, false);
  assert.equal(p.videos[0].pauses, 1);
  p.enter(0);
  assert.equal(p.videos[0].loads, 1);
  assert.equal(p.videos[0].plays, 2);
});

test('reduced motion and data saving leave posters visible without downloading loops', () => {
  for (const options of [{ reduced: true }, { saveData: true }]) {
    const p = page(options);
    p.enter(0);
    assert.equal(p.videos[0].source.src, '');
    assert.equal(p.videos[0].loads, 0);
    assert.equal(p.videos[0].plays, 0);
  }
  const p = page({ reduced: true });
  p.enter(0);
  p.motion.matches = false;
  p.motion.change();
  assert.equal(p.videos[0].loads, 1);
  p.motion.matches = true;
  p.motion.change();
  assert.equal(p.videos[0].pauses, 2);
});

test('background tabs pause loops and visible tabs resume without reloading', () => {
  const p = page();
  p.enter(0);
  p.document.hidden = true;
  p.events.get('visibilitychange')();
  assert.equal(p.videos[0].pauses, 1);
  p.document.hidden = false;
  p.events.get('visibilitychange')();
  assert.equal(p.videos[0].plays, 2);
  assert.equal(p.videos[0].loads, 1);
});

test('browsers without IntersectionObserver still load the original video sources', () => {
  const p = page({ observer: false });
  assert.ok(p.videos.every(video => video.loads === 1 && video.plays === 1));
});

test('mobile menu supports Escape and outside clicks without closing on inside clicks', () => {
  const p = page();
  p.menu.open = true;
  p.events.get('click')({ target: p.menu });
  assert.equal(p.menu.open, true);
  p.events.get('keydown')({ key: 'Escape' });
  assert.equal(p.menu.open, false);
  assert.equal(p.menu.focused, true);
  p.menu.open = true;
  p.events.get('click')({ target: {} });
  assert.equal(p.menu.open, false);
});

test('blocked autoplay is handled without an unhandled rejection', async () => {
  const p = page({ rejectPlay: true });
  p.enter(0);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(p.videos[0].loads, 1);
});
