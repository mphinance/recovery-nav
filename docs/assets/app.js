(function () {
  'use strict';
  var THROUGH = 'through Dec 2025';
  var DATA = 'data/';
  var FLAG_TEXT = {
    balance_mismatch: 'The balance we computed from receipts, interest and spending does not match the balance the county reported.',
    no_expenditure_text: 'This government reported no description of how the money is being used.',
    interest_excluded: 'Interest earned is not included in the source totals, so percent spent may look higher than it is.'
  };
  var S = { counties: [], items: [], cats: [], meta: null, missing: [], sort: { key: 'name', dir: 1 }, q: '', type: 'all' };
  var $view = document.getElementById('view'), $status = document.getElementById('status'), $nav = document.getElementById('nav');

  var usd0 = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
  var usdC = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 });
  var isNum = function (v) { return typeof v === 'number' && isFinite(v); };
  var money = function (v) { return isNum(v) ? usd0.format(v) : 'n/a'; };
  var moneyC = function (v) { return isNum(v) ? usdC.format(v) : 'n/a'; };
  var pct = function (v) { return isNum(v) ? (v * 100).toFixed(1) + '%' : 'n/a'; };

  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v === false || v == null) return;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    });
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) return c.forEach(function (x) { add(el, x); });
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  var safeUrl = function (u) { return typeof u === 'string' && /^https?:\/\//i.test(u) ? u : null; };

  function load(name) {
    return fetch(DATA + name + '.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(name + ' ' + r.status);
      return r.json();
    });
  }
  function init() {
    renderNav('');
    Promise.all(['counties', 'items', 'categories', 'meta'].map(function (n) {
      return load(n).catch(function () { S.missing.push(n); return null; });
    })).then(function (r) {
      S.counties = Array.isArray(r[0]) ? r[0] : [];
      S.items = Array.isArray(r[1]) ? r[1] : [];
      S.cats = Array.isArray(r[2]) ? r[2] : [];
      S.meta = r[3] && typeof r[3] === 'object' ? r[3] : null;
      S.byId = {}; S.counties.forEach(function (c) { S.byId[c.id] = c; });
      S.catById = {}; S.cats.forEach(function (c) { S.catById[c.id] = c; });
      var src = S.meta && Array.isArray(S.meta.sources) && S.meta.sources.filter(function (s) { return safeUrl(s.url); })[0];
      if (src) document.querySelectorAll('[data-wwlink]').forEach(function (a) { a.href = src.url; });
      route();
    });
    window.addEventListener('hashchange', route);
  }

  function parseHash() {
    var raw = location.hash.replace(/^#\/?/, ''), p = {};
    if (!raw) return { view: 'home' };
    if (raw === 'method') return { view: 'method' };
    if (raw === 'buying') return { view: 'buying' };
    raw.split('&').forEach(function (kv) { var i = kv.indexOf('='); if (i > 0) p[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); });
    if (p.county) return { view: 'county', id: p.county };
    if ('compare' in p) return { view: 'compare', ids: p.compare ? p.compare.split(',').slice(0, 4) : [] };
    if (raw === 'compare') return { view: 'compare', ids: [] };
    return { view: 'home' };
  }

  function renderNav(cur) {
    var links = [['home', '#/', 'All governments'], ['buying', '#buying', 'What counties are buying'], ['compare', '#compare=', 'Compare'], ['method', '#/method', 'Method']];
    $nav.textContent = '';
    links.forEach(function (l) { $nav.appendChild(h('a', { href: l[1], 'aria-current': cur === l[0] ? 'page' : false, text: l[2] })); });
  }

  function route() {
    var r = parseHash();
    renderNav(r.view === 'county' ? 'home' : r.view);
    $view.textContent = '';
    var fatal = S.missing.indexOf('counties') >= 0 || !S.counties.length;
    if (r.view === 'method') { $status.textContent = ''; viewMethod(); }
    else if (fatal) {
      $status.textContent = '';
      $view.appendChild(h('div', { class: 'notice', role: 'alert' },
        h('strong', { text: 'Data missing. ' }),
        'The settlement data file did not load or is empty. Try reloading in a minute. If it keeps happening, report it using the link at the bottom of the page.'));
    } else {
      $status.textContent = '';
      if (S.missing.length) $view.appendChild(h('div', { class: 'notice' }, 'Some data files did not load (' + S.missing.join(', ') + '). Parts of this page may be empty.'));
      if (r.view === 'county') viewCounty(r.id);
      else if (r.view === 'buying') viewBuying();
      else if (r.view === 'compare') viewCompare(r.ids);
      else viewHome();
    }
    document.title = (r.view === 'county' && S.byId && S.byId[r.id] ? S.byId[r.id].name + ' | ' : '') + 'Wisconsin Opioid Settlement Explorer';
    window.scrollTo(0, 0);
  }

  /* ---------- totals ---------- */
  function totals() {
    var m = (S.meta && S.meta.totals) || {}, cs = S.counties;
    var sum = function (k) { return cs.reduce(function (a, c) { return a + (isNum(c[k]) ? c[k] : 0); }, 0); };
    var rec = isNum(m.receipts) ? m.receipts : sum('receipts_total');
    var dis = isNum(m.disbursements) ? m.disbursements : sum('disbursements_total');
    var bal = isNum(m.balance) ? m.balance : sum('balance_dec_2025');
    var gov = isNum(m.governments) ? m.governments : cs.length;
    var intr = isNum(m.interest) ? m.interest : sum('interest_total');
    return { rec: rec, dis: dis, bal: bal, share: (rec + intr) > 0 ? dis / (rec + intr) : null, gov: gov };
  }
  function statStrip() {
    var t = totals();
    var items = [['Received', moneyC(t.rec), money(t.rec)], ['Spent', moneyC(t.dis), money(t.dis)], ['Unspent, as reported', moneyC(t.bal), money(t.bal)],
      ['Share spent', pct(t.share), 'of receipts plus interest'], ['Governments', String(t.gov), 'counties and municipalities']];
    return h('dl', { class: 'stats', 'aria-label': 'Statewide totals ' + THROUGH }, items.map(function (i) {
      return h('div', { class: 'stat' }, h('dt', { text: i[0] }), h('dd', null, i[1], h('small', { text: i[2] + (i[0] === 'Governments' ? '' : ', ' + THROUGH) })));
    }));
  }

  /* ---------- home ---------- */
  var COLS = [['name', 'Government'], ['receipts_total', 'Received'], ['disbursements_total', 'Spent'], ['balance_dec_2025', 'Balance'], ['pct_spent', 'Percent spent']];
  function viewHome() {
    $view.appendChild(h('h1', { text: 'Opioid settlement money in Wisconsin' }));
    $view.appendChild(h('p', { class: 'lede', text: 'How much each county and municipality has received from opioid settlements, how much it reports spending, and what is left. Figures are ' + THROUGH + '. Pick a name for the detail.' }));
    $view.appendChild(statStrip());
    var q = h('input', { type: 'search', id: 'q', value: S.q, autocomplete: 'off', placeholder: 'Type a name', oninput: function (e) { S.q = e.target.value; draw(); } });
    var ty = h('select', { id: 'ty', onchange: function (e) { S.type = e.target.value; draw(); } },
      [['all', 'Counties and municipalities'], ['county', 'Counties only'], ['municipality', 'Municipalities only']].map(function (o) { return h('option', { value: o[0], selected: S.type === o[0], text: o[1] }); }));
    $view.appendChild(h('div', { class: 'controls' }, h('label', { for: 'q' }, 'Search by name', q), h('label', { for: 'ty' }, 'Show', ty)));
    var count = h('p', { class: 'count', 'aria-live': 'polite' });
    var holder = h('div');
    $view.appendChild(count); $view.appendChild(holder);
    draw();
    function draw() {
      var needle = S.q.trim().toLowerCase();
      var rows = S.counties.filter(function (c) { return (S.type === 'all' || c.type === S.type) && (!needle || String(c.name).toLowerCase().indexOf(needle) >= 0); });
      var k = S.sort.key, d = S.sort.dir;
      rows.sort(function (a, b) {
        var x = a[k], y = b[k];
        if (k === 'name') return d * String(x).localeCompare(String(y));
        if (!isNum(x) && !isNum(y)) return 0; if (!isNum(x)) return 1; if (!isNum(y)) return -1;
        return d * (x - y);
      });
      count.textContent = rows.length + ' of ' + S.counties.length + ' governments shown';
      holder.textContent = '';
      if (!rows.length) { holder.appendChild(h('p', { text: 'No government matches that search.' })); return; }
      var tr = h('tr');
      COLS.forEach(function (c) {
        var on = S.sort.key === c[0];
        tr.appendChild(h('th', { scope: 'col', 'aria-sort': on ? (d > 0 ? 'ascending' : 'descending') : false },
          h('button', { class: 'sortbtn', type: 'button', onclick: function () {
            if (S.sort.key === c[0]) S.sort.dir *= -1; else S.sort = { key: c[0], dir: c[0] === 'name' ? 1 : -1 };
            draw(); var b = holder.querySelectorAll('.sortbtn')[COLS.indexOf(c)]; if (b) b.focus();
          } }, c[1], h('span', { class: 'arrow', 'aria-hidden': 'true', text: on ? (d > 0 ? '▲' : '▼') : '' }))));
      });
      var body = h('tbody', null, rows.map(function (c) {
        return h('tr', null,
          h('th', { scope: 'row', class: 'namecell' }, h('a', { href: '#county=' + encodeURIComponent(c.id), text: c.name }),
            c.flags && c.flags.length ? h('span', { class: 'flag-mark', title: 'Has data notes' }, 'Note') : null),
          h('td', { class: 'num', text: money(c.receipts_total) }), h('td', { class: 'num', text: money(c.disbursements_total) }),
          h('td', { class: 'num', text: money(c.balance_dec_2025) }), h('td', null, pctBar(c.pct_spent)));
      }));
      holder.appendChild(h('div', { class: 'scroll', role: 'region', 'aria-label': 'Governments table, scrolls sideways on small screens', tabindex: '0' },
        h('table', null, h('caption', { text: 'Opioid settlement money by government, ' + THROUGH }), h('thead', null, tr), body)));
    }
  }
  function pctBar(v) {
    if (!isNum(v)) return h('div', { class: 'pct' }, h('span', { class: 'val', text: 'n/a' }));
    var w = Math.max(0, Math.min(100, v * 100));
    return h('div', { class: 'pct' }, h('span', { class: 'track', 'aria-hidden': 'true' }, h('span', { class: 'fill', style: 'width:' + w + '%' })), h('span', { class: 'val', text: pct(v) }));
  }

  /* ---------- county ---------- */
  function yearsOf(c) { return Object.keys(c.by_year || {}).sort(); }
  function viewCounty(id) {
    var c = S.byId[id];
    $view.appendChild(h('a', { class: 'back', href: '#/', text: 'Back to all governments' }));
    if (!c) { $view.appendChild(h('div', { class: 'notice', role: 'alert' }, 'No government with that address was found.')); return; }
    $view.appendChild(h('h1', { text: c.name }));
    $view.appendChild(h('p', { class: 'lede', text: (c.type === 'county' ? 'County' : 'Municipality') + '. Figures are ' + THROUGH + '.' }));
    $view.appendChild(h('dl', { class: 'stats' }, [['Received', money(c.receipts_total)], ['Spent', money(c.disbursements_total)], ['Balance', money(c.balance_dec_2025)], ['Interest earned', money(c.interest_total)]].map(function (i) {
      return h('div', { class: 'stat' }, h('dt', { text: i[0] }), h('dd', { text: i[1] }));
    })));
    $view.appendChild(h('p', null, 'Percent spent: ', pctBar(c.pct_spent)));
    // flags
    $view.appendChild(h('h2', { text: 'Data notes' }));
    if (c.flags && c.flags.length) $view.appendChild(h('ul', { class: 'flaglist' }, c.flags.map(function (f) { return h('li', { text: FLAG_TEXT[f] || ('Note: ' + String(f).replace(/_/g, ' ') + '.') }); })));
    else $view.appendChild(h('p', { class: 'muted', text: 'No notes or known problems for this government.' }));
    // years
    $view.appendChild(h('h2', { text: 'By year' }));
    var ys = yearsOf(c);
    if (!ys.length) $view.appendChild(h('p', { class: 'muted', text: 'No by-year figures were reported.' }));
    else {
      $view.appendChild(yearChart(c, ys));
      var rows = ys.map(function (y) { var d = c.by_year[y] || {}; return h('tr', null, h('th', { scope: 'row', text: y }), h('td', { class: 'num', text: money(d.receipts) }), h('td', { class: 'num', text: money(d.disbursements) }), h('td', { class: 'num', text: money(d.interest) })); });
      $view.appendChild(h('div', { class: 'scroll', role: 'region', tabindex: '0', 'aria-label': 'By-year table' },
        h('table', null, h('caption', { text: 'Receipts and disbursements by year' }), h('thead', null, h('tr', null, ['Year', 'Received', 'Spent', 'Interest'].map(function (t) { return h('th', { scope: 'col', text: t }); }))), h('tbody', null, rows))));
    }
    if (safeUrl(c.report_url)) $view.appendChild(h('p', null, h('a', { href: c.report_url, rel: 'noopener' }, 'County filing'), ' (' + (c.source || 'source') + ')'));
    else if (c.source) $view.appendChild(h('p', { class: 'muted', text: 'Source: ' + c.source }));
    // items
    $view.appendChild(h('h2', { text: 'Reported spending items' }));
    $view.appendChild(h('p', { class: 'notice' }, h('strong', { text: 'Reported initiative, not necessarily cash spent. ' }), 'Items use the county\'s own wording. Amounts and periods vary and may overlap, so do not add them up as money spent.'));
    var mine = S.items.filter(function (i) { return i.county_id === c.id; });
    if (!mine.length) { $view.appendChild(h('p', { class: 'muted', text: 'No spending items were reported for this government.' })); return; }
    var groups = {}; mine.forEach(function (i) { (groups[i.category || 'other'] = groups[i.category || 'other'] || []).push(i); });
    Object.keys(groups).sort(function (a, b) { return catLabel(a).localeCompare(catLabel(b)); }).forEach(function (k) {
      $view.appendChild(h('h3', { text: catLabel(k) + ' (' + groups[k].length + ')' }));
      $view.appendChild(h('ul', { class: 'items' }, groups[k].map(function (i) {
        return h('li', { class: 'item' }, h('div', { text: i.text || '' }),
          h('div', { class: 'meta' }, h('span', { class: 'amt', text: isNum(i.amount) ? money(i.amount) : 'No amount given' }), h('span', { class: 'tag', text: 'Period: ' + (i.period_label || 'not stated') }), h('span', { class: 'tag', text: 'Reported initiative' })));
      })));
    });
  }
  function catLabel(id) { return (S.catById[id] && S.catById[id].label) || String(id).replace(/_/g, ' '); }

  function yearChart(c, ys) {
    var NS = 'http://www.w3.org/2000/svg', W = 480, H = 220, L = 52, B = 28, T = 10;
    var max = 0; ys.forEach(function (y) { var d = c.by_year[y] || {}; max = Math.max(max, d.receipts || 0, d.disbursements || 0); });
    if (!max) return h('p', { class: 'muted', text: 'No amounts to chart.' });
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); svg.setAttribute('class', 'chart'); svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Bar chart of receipts and disbursements by year. The same numbers are in the table below.');
    function el(n, a, t) { var e = document.createElementNS(NS, n); Object.keys(a).forEach(function (k) { e.setAttribute(k, a[k]); }); if (t != null) e.textContent = t; svg.appendChild(e); return e; }
    var defs = el('defs', {}); var pat = document.createElementNS(NS, 'pattern');
    pat.setAttribute('id', 'hatch'); pat.setAttribute('width', 6); pat.setAttribute('height', 6); pat.setAttribute('patternUnits', 'userSpaceOnUse'); pat.setAttribute('patternTransform', 'rotate(45)');
    var pr = document.createElementNS(NS, 'rect'); pr.setAttribute('width', 3); pr.setAttribute('height', 6); pr.setAttribute('fill', 'var(--dis)'); pat.appendChild(pr); defs.appendChild(pat);
    var ph = H - B - T, pw = W - L - 8, gw = pw / ys.length, bw = Math.min(40, gw / 2.6);
    el('line', { x1: L, x2: W - 8, y1: H - B, y2: H - B, class: 'axis' });
    el('text', { x: L - 6, y: T + 8, 'text-anchor': 'end' }, moneyC(max)); el('text', { x: L - 6, y: H - B, 'text-anchor': 'end' }, '$0');
    ys.forEach(function (y, i) {
      var d = c.by_year[y] || {}, cx = L + gw * i + gw / 2;
      [['receipts', 'rec', -bw], ['disbursements', 'dis', 0]].forEach(function (s) {
        var v = d[s[0]]; if (!isNum(v)) return; var hh = v / max * ph;
        el('rect', { x: cx + s[2], y: H - B - hh, width: bw, height: hh, class: s[1] });
      });
      el('text', { x: cx, y: H - 10, 'text-anchor': 'middle' }, y);
    });
    return h('figure', { style: 'margin:0 0 1rem' }, svg, h('div', { class: 'legend' }, h('span', null, h('i', { class: 'sw rec' }), 'Received'), h('span', null, h('i', { class: 'sw dis' }), 'Spent (hatched)')));
  }

  /* ---------- buying ---------- */
  function viewBuying() {
    $view.appendChild(h('h1', { text: 'What counties are buying' }));
    $view.appendChild(h('p', { class: 'notice' }, h('strong', { text: 'Read this first. ' }), 'These are initiatives the counties reported in their own words, grouped by us into categories. Amounts are county-reported initiatives covering mixed periods, and not every item has an amount. They are not a total of cash spent.'));
    if (!S.items.length) { $view.appendChild(h('p', { class: 'muted', text: 'No spending item data is available yet.' })); return; }
    var agg = {}; S.items.forEach(function (i) {
      var k = i.category || 'other', a = agg[k] = agg[k] || { n: 0, sum: 0, noamt: 0, cs: {} };
      a.n++; if (isNum(i.amount)) a.sum += i.amount; else a.noamt++; a.cs[i.county_id] = (a.cs[i.county_id] || 0) + (isNum(i.amount) ? i.amount : 0);
    });
    var keys = Object.keys(agg).sort(function (a, b) { return agg[b].sum - agg[a].sum; });
    var max = Math.max.apply(null, keys.map(function (k) { return agg[k].sum; })) || 1;
    var rows = keys.map(function (k) {
      var a = agg[k], w = a.sum / max * 100;
      return h('tr', null, h('th', { scope: 'row', class: 'namecell' }, catLabel(k), S.catById[k] && S.catById[k].description ? h('div', { class: 'muted', style: 'font-weight:400;font-size:.85rem', text: S.catById[k].description }) : null),
        h('td', { class: 'num', text: String(a.n) }), h('td', { class: 'num', text: String(Object.keys(a.cs).length) }), h('td', { class: 'num', text: String(a.noamt) }),
        h('td', null, h('div', { class: 'pct' }, h('span', { class: 'track', 'aria-hidden': 'true' }, h('span', { class: 'fill', style: 'width:' + w + '%' })), h('span', { class: 'val', style: 'min-width:5rem', text: moneyC(a.sum) }))));
    });
    $view.appendChild(h('div', { class: 'scroll', role: 'region', tabindex: '0', 'aria-label': 'Categories table' }, h('table', null,
      h('caption', { text: 'Reported initiatives by category, sorted by listed amount' }),
      h('thead', null, h('tr', null, ['Category', 'Items', 'Counties', 'Items with no amount', 'Listed amount'].map(function (t) { return h('th', { scope: 'col', text: t }); }))), h('tbody', null, rows))));
    $view.appendChild(h('h2', { text: 'Who reports the most in each category' }));
    $view.appendChild(h('div', { class: 'grid' }, keys.map(function (k) {
      var top = Object.keys(agg[k].cs).sort(function (a, b) { return agg[k].cs[b] - agg[k].cs[a]; }).slice(0, 5);
      return h('section', { class: 'card' }, h('h3', { text: catLabel(k) }), h('ol', null, top.map(function (id) {
        var c = S.byId[id]; return h('li', null, c ? h('a', { href: '#county=' + encodeURIComponent(id), text: c.name }) : id, ' ' + (agg[k].cs[id] ? '(' + moneyC(agg[k].cs[id]) + ' listed)' : '(no amount listed)'));
      })));
    })));
  }

  /* ---------- compare ---------- */
  function viewCompare(ids) {
    ids = ids.filter(function (id) { return S.byId[id]; });
    $view.appendChild(h('h1', { text: 'Compare counties' }));
    $view.appendChild(h('p', { class: 'lede', text: 'Pick 2 to 4 governments to see them side by side. Figures are ' + THROUGH + '.' }));
    var fs = h('fieldset', { class: 'pickers' }, h('legend', { text: 'Choose up to 4' }));
    var msg = h('p', { class: 'count', 'aria-live': 'polite' });
    var filter = h('input', { type: 'search', id: 'pf', placeholder: 'Filter the list', 'aria-label': 'Filter the list of governments', oninput: function (e) {
      var n = e.target.value.toLowerCase(); grid.querySelectorAll('label').forEach(function (l) { l.hidden = l.textContent.toLowerCase().indexOf(n) < 0; });
    } });
    var grid = h('div', { class: 'pickgrid' }, S.counties.map(function (c) {
      return h('label', null, h('input', { type: 'checkbox', value: c.id, checked: ids.indexOf(c.id) >= 0, onchange: function (e) {
        var cur = ids.slice();
        if (e.target.checked) { if (cur.length >= 4) { e.target.checked = false; msg.textContent = 'You can compare at most 4. Uncheck one first.'; return; } cur.push(c.id); }
        else cur = cur.filter(function (x) { return x !== c.id; });
        location.hash = 'compare=' + cur.map(encodeURIComponent).join(',');
      } }), c.name);
    }));
    fs.appendChild(filter); fs.appendChild(grid); $view.appendChild(fs); $view.appendChild(msg);
    if (ids.length < 2) { $view.appendChild(h('p', { class: 'muted', text: ids.length ? 'Pick at least one more.' : 'Nothing picked yet.' })); return; }
    var cs = ids.map(function (id) { return S.byId[id]; });
    var spec = [['Received', function (c) { return money(c.receipts_total); }], ['Spent', function (c) { return money(c.disbursements_total); }], ['Balance', function (c) { return money(c.balance_dec_2025); }],
      ['Interest earned', function (c) { return money(c.interest_total); }], ['Percent spent', function (c) { return pctBar(c.pct_spent); }], ['Data notes', function (c) { return c.flags && c.flags.length ? c.flags.length + ' note' + (c.flags.length > 1 ? 's' : '') : 'None'; }]];
    var allYears = {}; cs.forEach(function (c) { yearsOf(c).forEach(function (y) { allYears[y] = 1; }); });
    Object.keys(allYears).sort().forEach(function (y) {
      spec.push(['Received ' + y, function (c) { var d = c.by_year && c.by_year[y]; return d ? money(d.receipts) : 'n/a'; }]);
      spec.push(['Spent ' + y, function (c) { var d = c.by_year && c.by_year[y]; return d ? money(d.disbursements) : 'n/a'; }]);
    });
    spec.push(['Reported items', function (c) { return String(S.items.filter(function (i) { return i.county_id === c.id; }).length); }]);
    var head = h('tr', null, h('th', { scope: 'col', text: 'Measure' }), cs.map(function (c) { return h('th', { scope: 'col' }, h('a', { href: '#county=' + encodeURIComponent(c.id), text: c.name })); }));
    var body = spec.map(function (s) { return h('tr', null, h('th', { scope: 'row', text: s[0] }), cs.map(function (c) { var v = s[1](c); return h('td', { class: 'num' }, v); })); });
    $view.appendChild(h('div', { class: 'scroll', role: 'region', tabindex: '0', 'aria-label': 'Comparison table' }, h('table', null, h('caption', { text: 'Side by side comparison' }), h('thead', null, head), h('tbody', null, body))));
    $view.appendChild(h('h2', { text: 'Reported items by category' }));
    $view.appendChild(h('p', { class: 'notice' }, h('strong', { text: 'Reported initiative, not necessarily cash spent. ' }), 'Counts of items in the county\'s own reports.'));
    var catIds = {}; S.items.forEach(function (i) { if (ids.indexOf(i.county_id) >= 0) catIds[i.category || 'other'] = 1; });
    var ck = Object.keys(catIds).sort();
    if (!ck.length) $view.appendChild(h('p', { class: 'muted', text: 'None of these governments reported spending items.' }));
    else $view.appendChild(h('div', { class: 'scroll', role: 'region', tabindex: '0', 'aria-label': 'Items by category' }, h('table', null, h('caption', { text: 'Number of reported items, and listed amount where given' }),
      h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Category' }), cs.map(function (c) { return h('th', { scope: 'col', text: c.name }); }))),
      h('tbody', null, ck.map(function (k) {
        return h('tr', null, h('th', { scope: 'row', text: catLabel(k) }), cs.map(function (c) {
          var m = S.items.filter(function (i) { return i.county_id === c.id && (i.category || 'other') === k; });
          var sum = m.reduce(function (a, i) { return a + (isNum(i.amount) ? i.amount : 0); }, 0);
          return h('td', { class: 'num', text: m.length ? m.length + (sum ? ' (' + moneyC(sum) + ')' : '') : 'none' });
        }));
      })))));
  }

  /* ---------- method ---------- */
  function viewMethod() {
    $view.appendChild(h('h1', { text: 'Methodology' }));
    $view.appendChild(h('p', { text: 'The money figures come from the Wisconsin Watch opioid settlement tracker, which compiles reports that counties and municipalities file with the state. Where we could, we checked numbers against the filings themselves.' }));
    $view.appendChild(h('ul', null,
      h('li', null, 'Percent spent is spent divided by received plus interest earned. We compute it ourselves and compare it to the source figure.'),
      h('li', null, 'Balance is the figure reported for December 2025. When it does not match our own arithmetic, the government gets a data note.'),
      h('li', null, 'Spending items are the county\'s own words about initiatives. Categories are our grouping. Item amounts cover mixed periods and are not cash spent.'),
      h('li', null, 'This is unofficial and may contain errors. If you find one, report it using the link below.')));
    var m = S.meta;
    if (m && Array.isArray(m.caveats) && m.caveats.length) { $view.appendChild(h('h2', { text: 'Known caveats' })); $view.appendChild(h('ul', null, m.caveats.map(function (c) { return h('li', { text: String(c) }); }))); }
    if (m && Array.isArray(m.sources) && m.sources.length) {
      $view.appendChild(h('h2', { text: 'Sources' }));
      $view.appendChild(h('ul', null, m.sources.map(function (s) { return h('li', null, safeUrl(s.url) ? h('a', { href: s.url, rel: 'noopener', text: s.name || s.url }) : String(s.name || ''), s.retrieved_at ? ', retrieved ' + s.retrieved_at : ''); })));
    }
    if (m && m.generated_at) $view.appendChild(h('p', { class: 'muted', text: 'Data generated ' + m.generated_at + (m.method_version ? ', method version ' + m.method_version : '') + '.' }));
    $view.appendChild(h('h2', { text: 'Full documentation' }));
    $view.appendChild(h('ul', null,
      h('li', null, h('a', { href: 'https://github.com/mphinance/recovery-nav/blob/main/docs/methodology.md', rel: 'noopener' }, 'Methodology')),
      h('li', null, h('a', { href: 'https://github.com/mphinance/recovery-nav/blob/main/docs/data-dictionary.md', rel: 'noopener' }, 'Data dictionary'))));
    $view.appendChild(h('p', null, h('a', { href: 'https://github.com/mphinance/recovery-nav/issues', rel: 'noopener' }, 'Report an error')));
  }

  init();
})();
