const form = document.querySelector('#search-form');
const input = document.querySelector('#query');
const status = document.querySelector('#status');
let controller;
let sequence = 0;
const currency = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 2});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function card(product) {
  const article = element('article', `product${product.available ? '' : ' unavailable'}`);
  const top = element('div', 'product-top');
  top.append(element('span', 'category', product.category), element('span', 'stock', product.available ? 'In stock' : product.availability === 'unknown' ? 'Stock unconfirmed' : 'Out of stock'));
  article.append(top, element('h3', '', product.name), element('p', 'size', product.size));
  const price = element('div', 'price-row');
  price.append(element('span', 'price', product.price === null ? 'Price under review' : currency.format(product.price)), element('span', 'brand', product.brand));
  article.append(price);
  if (product.price_warning) article.append(element('p', 'note', 'Price needs verification.'));
  if (!product.available) article.append(element('p', 'note', product.restock_eta ? `Estimated return: ${product.restock_eta}` : product.restock_note || 'No confirmed restock date.'));
  const details = element('details');
  details.append(element('summary', '', 'Why this match?'), element('p', '', product.reasons.join(' · ')), element('p', 'sku', product.sku_id));
  article.append(details);
  return article;
}

function section(id, products) {
  const container = document.querySelector(`#${id}`);
  container.replaceChildren(...products.map(card));
  document.querySelector(`#${id}-section`).hidden = products.length === 0;
}

async function search(query) {
  document.body.classList.toggle('searched', Boolean(query.trim()));
  controller?.abort();
  controller = new AbortController();
  const request = ++sequence;
  status.textContent = query.trim() ? 'Finding your favourites…' : 'Type a product, brand, or a familiar name to get started.';
  section('results', []);
  section('unavailable', []);
  document.querySelector('#interpretation').replaceChildren();
  if (!query.trim()) return;
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {signal: controller.signal});
    const data = await response.json();
    if (request !== sequence) return;
    if (!response.ok) throw new Error(data.error || 'Search is unavailable.');
    section('results', data.results);
    section('unavailable', data.unavailable);
    document.querySelector('#count').textContent = `${data.results.length} ${data.results.length === 1 ? 'match' : 'matches'}`;
    status.textContent = data.results.length ? `Matches for “${query}”` : data.unavailable.length ? 'We found matches, but none are confirmed in stock.' : 'No close matches. Try another spelling, a broader product name, or a different brand.';
    const notes = [];
    if (data.corrections.length) notes.push(`Interpreted: ${data.corrections.map(c => `${c.from} → ${c.to}`).join(', ')}`);
    if (data.brand) notes.push(`Brand: ${data.brand}`);
    const c = data.constraints;
    if (c.max_price !== null) notes.push(`${c.max_inclusive ? 'Up to' : 'Under'} ${currency.format(c.max_price)}`);
    if (c.min_price !== null) notes.push(`${c.min_inclusive ? 'At least' : 'Above'} ${currency.format(c.min_price)}`);
    if (c.quantity !== null) notes.push(`Pack: ${c.quantity} ${c.unit}`);
    if (c.cheap) notes.push('Lower pack prices first');
    notes.push(...data.warnings);
    if (notes.length) document.querySelector('#interpretation').append(element('p', 'interpretation', notes.join(' · ')));
    document.querySelector('#snapshot').textContent = `Catalog snapshot · ${data.as_of}`;
  } catch (error) {
    if (error.name !== 'AbortError' && request === sequence) status.textContent = `Couldn't search. ${error.message} Please try again.`;
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  const query = input.value.trim();
  const url = new URL(location.href);
  if (query) url.searchParams.set('q', query); else url.searchParams.delete('q');
  history.replaceState(null, '', url);
  search(query);
});
document.querySelectorAll('[data-query]').forEach(button => button.addEventListener('click', () => {
  input.value = button.dataset.query;
  form.requestSubmit();
}));
const initial = new URL(location.href).searchParams.get('q');
if (initial) { input.value = initial; search(initial); }
