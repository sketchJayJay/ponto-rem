function moneyBR(value){
  const number = Number(value || 0);
  return number.toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
}

document.addEventListener('click', (event) => {
  const addVariant = event.target.closest('[data-add-variant]');
  if(addVariant){
    const template = document.querySelector('#variant-template');
    const target = document.querySelector('[data-variants]');
    target.appendChild(template.content.cloneNode(true));
  }
  const addSale = event.target.closest('[data-add-sale-row]');
  if(addSale){
    const template = document.querySelector('#sale-row-template');
    const target = document.querySelector('[data-sale-items]');
    target.appendChild(template.content.cloneNode(true));
    updateSaleTotal();
  }
  const remove = event.target.closest('[data-remove-row]');
  if(remove){
    const row = remove.closest('.variant-row, .sale-row');
    if(row) row.remove();
    updateSaleTotal();
  }
});

document.addEventListener('change', (event) => {
  const select = event.target.closest('[data-sale-select]');
  if(select){
    const opt = select.selectedOptions[0];
    const row = select.closest('.sale-row');
    const priceInput = row.querySelector('[data-sale-price]');
    if(opt && opt.dataset.price) priceInput.value = Number(opt.dataset.price).toFixed(2);
    updateSaleTotal();
  }
});

document.addEventListener('input', (event) => {
  if(event.target.matches('[data-sale-qty], [data-sale-price], [data-sale-discount]')) updateSaleTotal();
});

function updateSaleTotal(){
  const form = document.querySelector('[data-sale-form]');
  if(!form) return;
  let subtotal = 0;
  form.querySelectorAll('.sale-row').forEach(row => {
    const qty = Number(row.querySelector('[data-sale-qty]')?.value || 0);
    const price = Number(row.querySelector('[data-sale-price]')?.value || 0);
    subtotal += qty * price;
  });
  const discount = Number(form.querySelector('[data-sale-discount]')?.value || 0);
  const total = Math.max(subtotal - discount, 0);
  const target = form.querySelector('[data-sale-total]');
  if(target) target.textContent = moneyBR(total);
}

setTimeout(() => {
  document.querySelectorAll('.toast').forEach(t => t.style.display='none');
}, 4500);

updateSaleTotal();

const INTEREST_KEY = 'rem_interest_bag';

function getInterestBag(){
  try {
    return JSON.parse(localStorage.getItem(INTEREST_KEY) || '[]');
  } catch(e){
    return [];
  }
}

function saveInterestBag(items){
  localStorage.setItem(INTEREST_KEY, JSON.stringify(items));
}

function openInterestDrawer(){
  document.querySelector('[data-interest-drawer]')?.classList.add('open');
  document.querySelector('[data-interest-overlay]')?.classList.add('show');
}

function closeInterestDrawer(){
  document.querySelector('[data-interest-drawer]')?.classList.remove('open');
  document.querySelector('[data-interest-overlay]')?.classList.remove('show');
}

function renderInterestBag(){
  const items = getInterestBag();
  const count = document.querySelector('[data-interest-count]');
  if(count) count.textContent = items.length;
  const target = document.querySelector('[data-interest-items]');
  if(target){
    if(!items.length){
      target.innerHTML = '<div class="empty">Sua lista está vazia. Adicione modelos para enviar no WhatsApp.</div>';
    } else {
      target.innerHTML = items.map((item, index) => `
        <div class="interest-item">
          <div class="interest-item-head">
            <div>
              <strong>${item.name}</strong>
              <small>${item.price || ''}</small>
            </div>
            <button class="remove-link" type="button" data-interest-remove="${index}">Remover</button>
          </div>
          <small>${item.color ? 'Cor: ' + item.color : 'Cor a definir'}${item.size ? ' • Tam. ' + item.size : ''}</small>
          <a href="${item.link || '#'}"><small>Ver modelo</small></a>
        </div>
      `).join('');
    }
  }
  const whatsappBtn = document.querySelector('[data-interest-whatsapp]');
  if(whatsappBtn){
    if(items.length){
      const phone = whatsappBtn.dataset.whatsapp;
      const lines = items.map((item, idx) => `${idx + 1}. ${item.name}${item.color ? ' | Cor: ' + item.color : ''}${item.size ? ' | Tam: ' + item.size : ''}`);
      const message = encodeURIComponent(`Olá! Tenho interesse nesses modelos da Ponto REM:

${lines.join('\n')}

Pode me atender?`);
      whatsappBtn.href = `https://wa.me/${phone}?text=${message}`;
      whatsappBtn.classList.remove('disabled');
    } else {
      whatsappBtn.href = '#';
      whatsappBtn.classList.add('disabled');
    }
  }
}

function addToInterestBag(payload){
  const items = getInterestBag();
  const duplicate = items.some(item => item.name === payload.name && (item.color || '') === (payload.color || '') && (item.size || '') === (payload.size || ''));
  if(!duplicate) items.push(payload);
  saveInterestBag(items);
  renderInterestBag();
  openInterestDrawer();
}

document.addEventListener('click', (event) => {
  const openBtn = event.target.closest('[data-interest-open]');
  if(openBtn) openInterestDrawer();
  const closeBtn = event.target.closest('[data-interest-close], [data-interest-overlay]');
  if(closeBtn) closeInterestDrawer();

  const addInterest = event.target.closest('[data-interest-add]');
  if(addInterest){
    const detail = addInterest.hasAttribute('data-detail-product');
    const color = detail ? document.querySelector('[data-detail-color]')?.value || '' : '';
    const size = detail ? document.querySelector('[data-detail-size]')?.value || '' : '';
    addToInterestBag({
      id: addInterest.dataset.productId,
      name: addInterest.dataset.productName,
      price: addInterest.dataset.productPrice,
      link: addInterest.dataset.productLink,
      color,
      size
    });
  }

  const removeInterest = event.target.closest('[data-interest-remove]');
  if(removeInterest){
    const index = Number(removeInterest.dataset.interestRemove);
    const items = getInterestBag();
    items.splice(index, 1);
    saveInterestBag(items);
    renderInterestBag();
  }

  const clearInterest = event.target.closest('[data-interest-clear]');
  if(clearInterest){
    saveInterestBag([]);
    renderInterestBag();
  }
});

renderInterestBag();

function updateReserveWhatsApp(){
  const button = document.querySelector('[data-reserve-whatsapp]');
  if(!button) return;
  const color = document.querySelector('[data-detail-color]')?.value || '';
  const size = document.querySelector('[data-detail-size]')?.value || '';
  const product = button.dataset.productName || 'modelo';
  const store = button.dataset.storeName || 'Ponto REM';
  const phone = button.dataset.whatsapp;
  const extra = `${color ? ' Cor: ' + color + '.' : ''}${size ? ' Tamanho: ' + size + '.' : ''}`;
  const message = encodeURIComponent(`Olá! Quero reservar o ${product}.${extra} Vi no catálogo da ${store}. Está disponível?`);
  button.href = `https://wa.me/${phone}?text=${message}`;
}

document.addEventListener('change', (event) => {
  if(event.target.matches('[data-detail-color], [data-detail-size]')) updateReserveWhatsApp();
});

function startBannerCarousel(){
  const carousel = document.querySelector('[data-banner-carousel]');
  if(!carousel) return;
  const slides = [...carousel.querySelectorAll('.banner-slide')];
  const dots = [...carousel.querySelectorAll('[data-banner-dot]')];
  let index = 0;
  function showSlide(next){
    index = next;
    slides.forEach((slide, i) => slide.classList.toggle('active', i === index));
    dots.forEach((dot, i) => dot.classList.toggle('active', i === index));
  }
  dots.forEach(dot => dot.addEventListener('click', () => showSlide(Number(dot.dataset.bannerDot || 0))));
  setInterval(() => showSlide((index + 1) % slides.length), 5200);
}

updateReserveWhatsApp();
startBannerCarousel();
