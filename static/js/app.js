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
