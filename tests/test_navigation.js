const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise navigation state and focus without loading monitoring or changing data.
const classes = new Set(), listeners = {}, saved = new Map();
let focused, resize;
function node(name) {
  return { textContent: name, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }, focus() { focused = name; } };
}
const elements = new Map(['main', '#toggle-nav', '#close-nav', '#nav-scrim', '#compact-nav'].map(name => [name, node(name)]));
const menus = [node('Overview'), node('Storage')];
const context = vm.createContext({
  document: {
    body: { classList: {
      contains: name => classes.has(name), add: name => classes.add(name), remove: name => classes.delete(name),
      toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); }
    } },
    querySelector: name => elements.get(name), querySelectorAll: () => menus,
    addEventListener(name, handler) { (listeners[name] ||= []).push(handler); }
  },
  window: { matchMedia: () => ({ addEventListener(name, handler) { resize = handler; } }) },
  localStorage: { getItem: name => saved.get(name), setItem: (name, value) => saved.set(name, value) }
});
const source = fs.readFileSync('static/navigation.js', 'utf8');
vm.runInContext(source.slice(source.indexOf('// Compact-screen navigation')), context);
const open = elements.get('#toggle-nav'), main = elements.get('main');
open.onclick();
assert.equal(main.inert, true);
assert.equal(open.attrs['aria-expanded'], 'true');
assert.equal(focused, '#close-nav');
listeners.keydown[0]({ key: 'Escape' });
assert.equal(main.inert, false);
assert.equal(focused, '#toggle-nav');
open.onclick();
listeners.click[0]({ target: { closest: () => menus[1] } });
assert.equal(classes.has('nav-open'), false);
assert.equal(main.inert, false);
open.onclick();
elements.get('#nav-scrim').onclick();
assert.equal(open.attrs['aria-expanded'], 'false');
open.onclick(); resize({ matches: true });
assert.equal(main.inert, false, 'Widening the window must release inert content');

const compact = elements.get('#compact-nav');
compact.onclick();
assert.equal(classes.has('sidebar-compact'), true);
assert.equal(compact.attrs['aria-label'], 'Expand sidebar');
assert.equal(compact.attrs['aria-expanded'], 'false');
assert.equal(saved.get('pulse.sidebarCompact'), 'true');
assert.equal(menus[1].attrs['data-help'], 'Storage');
compact.onclick();
assert.equal(compact.attrs['aria-label'], 'Collapse sidebar');
assert.equal(saved.get('pulse.sidebarCompact'), 'false');
assert.equal(menus[1].attrs['data-help'], undefined);
saved.set('pulse.sidebarCompact', 'true');
vm.runInContext(source.slice(source.indexOf('// A compact rail')), context);
assert.equal(classes.has('sidebar-compact'), true, 'A new session restores the saved rail preference');
console.log('Navigation drawer, focus, resize, and persisted compact rail checks passed.');
