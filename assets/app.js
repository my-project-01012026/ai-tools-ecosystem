"use strict";
// Isolated, arithmetic-only preview; no network, wallet or user data.
const slider=document.querySelector('#burn-months');
if(slider){
  const output=document.querySelector('#months-value');
  const supply=document.querySelector('#supply-value');
  const burned=document.querySelector('#burned-value');
  const reserve=document.querySelector('#reserve-value');
  const fmt=new Intl.NumberFormat(document.documentElement.lang||'en');
  const valid=slider.min==='0' && slider.max==='120' && slider.step==='1' && output&&supply&&burned&&reserve;
  function update(){
   const n=Number(slider.value);
   if(!valid||!Number.isSafeInteger(n)||n<0||n>120){
     slider.disabled=true;slider.setAttribute('aria-invalid','true');
     for(const v of [output,supply,burned,reserve])if(v)v.textContent='—';return;
   }
   slider.removeAttribute('aria-invalid');
   output.textContent=fmt.format(n);
   burned.textContent=fmt.format(1_000_000*n);
   reserve.textContent=fmt.format(120_000_000-1_000_000*n);
   supply.textContent=fmt.format(1_000_000_000-1_000_000*n);
  }
  slider.addEventListener('input',update);update();
}
