import{o as e}from"./activity-BHXaA2GE.js";import{t}from"./nativeActivity-C8SyKiPs.js";(function(){let n=document.querySelector(`[data-site-builder]`);if(!n)return;t();let r=n.querySelector(`[data-preview-frame]`),i=r?r.querySelector(`iframe`):null,a=n.querySelectorAll(`[data-preview-size]`),o=n.querySelector(`[data-blocks-json-field]`),s=n.querySelector(`[data-block-editor-list]`),c=n.querySelector(`[data-block-properties]`),l=n.querySelector(`[data-builder-empty]`),u=n.querySelector(`[data-builder-status]`),d=n.querySelector(`[data-block-count]`),f=n.querySelectorAll(`[data-block-preset]`),p=n.querySelector(`[data-asset-upload-form]`),m=n.querySelector(`[data-asset-list]`),h=-1,g=_();a.forEach(e=>{e.addEventListener(`click`,()=>{a.forEach(e=>e.classList.remove(`active`)),e.classList.add(`active`),r.classList.remove(`is-desktop`,`is-tablet`,`is-mobile`),r.classList.add(`is-${e.dataset.previewSize||`desktop`}`)})}),n.querySelectorAll(`[data-builder-action]`).forEach(e=>{e.addEventListener(`click`,async()=>{let t=e.dataset.builderAction;t===`save`&&await E(n.dataset.saveUrl,`Bozza salvata.`),t===`publish`&&await E(n.dataset.publishUrl,`Modifiche pubblicate.`),t===`refresh-preview`&&D()})}),n.querySelectorAll(`[data-restore-revision]`).forEach(t=>{t.addEventListener(`submit`,async n=>{n.preventDefault();let r=await e(`Ripristino della revisione del sito…`,async()=>(await fetch(t.action,{method:`POST`,headers:{Accept:`application/json`}})).json());N(r.message||`Revisione ripristinata.`,r.ok?`success`:`danger`),r.ok&&window.location.reload()})}),f.forEach(e=>{e.addEventListener(`click`,()=>{try{g.push(JSON.parse(e.dataset.blockPreset||`{}`))}catch{g.push({type:`rich_text`,title:`Nuova sezione`,text:``})}h=g.length-1,v(),y(),N(`Blocco aggiunto alla pagina selezionata.`,`success`)})}),p&&p.addEventListener(`submit`,async t=>{t.preventDefault();let n=new FormData(p),r=await e(`Caricamento dell’immagine del sito…`,async()=>(await fetch(`/sito-studio/api/assets/upload`,{method:`POST`,body:n,headers:{Accept:`application/json`}})).json());if(!r.ok){N(r.error||`Caricamento immagine non riuscito.`,`danger`);return}O(r.asset),p.reset(),N(r.message||`Immagine caricata.`,`success`)}),m&&m.addEventListener(`click`,e=>{let t=e.target.closest(`[data-asset-url]`);!t||h<0||!g[h]||(g[h].image_url=t.dataset.assetUrl||``,g[h].image_alt=t.dataset.assetAlt||``,v(),y(),N(`Immagine collegata al blocco selezionato.`,`success`))});function _(){if(!o)return[];try{let e=JSON.parse(o.value||`[]`);return Array.isArray(e)?e:[]}catch{return[]}}function v(){o&&(o.value=JSON.stringify(g,null,2)),d&&(d.textContent=String(g.length))}function y(){s&&(s.innerHTML=``,l&&(l.hidden=g.length>0),g.forEach((e,t)=>{let n=document.createElement(`article`);n.className=`studio-block-editor-row${t===h?` is-selected`:``}`,n.innerHTML=`
        <button class="studio-block-select" type="button" data-action="select">
          <span>
            <strong>${F(e.title||e.type||`Blocco`)}</strong>
            <small>${F(e.type||``)}</small>
          </span>
          <span class="badge text-bg-light">${t+1}</span>
        </button>
        <div class="studio-block-editor-actions">
          <button class="btn btn-sm btn-outline-secondary" type="button" data-action="up">Su</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" data-action="down">Gi&ugrave;</button>
          <button class="btn btn-sm btn-outline-primary" type="button" data-action="duplicate">Duplica</button>
          <button class="btn btn-sm btn-outline-danger" type="button" data-action="delete">Elimina</button>
        </div>
      `,n.querySelectorAll(`[data-action]`).forEach(e=>{e.addEventListener(`click`,()=>b(e.dataset.action,t))}),s.appendChild(n)}),x(),v())}function b(e,t){e===`select`&&(h=t),e===`delete`&&(g.splice(t,1),h=Math.min(g.length-1,t)),e===`duplicate`&&(g.splice(t+1,0,JSON.parse(JSON.stringify(g[t]))),h=t+1),e===`up`&&t>0&&([g[t-1],g[t]]=[g[t],g[t-1]],h=t-1),e===`down`&&t<g.length-1&&([g[t+1],g[t]]=[g[t],g[t+1]],h=t+1),y()}function x(){if(!c)return;let e=h>=0?g[h]:null;if(!e){c.innerHTML=`<div class="text-muted">Nessun blocco selezionato.</div>`;return}c.innerHTML=`
      <div class="studio-block-properties-grid">
        ${k(`type`,`Tipo blocco`,e.type||``,!0)}
        ${k(`title`,`Titolo`,e.title||``)}
        ${k(`subtitle`,`Sottotitolo`,e.subtitle||``)}
        ${A(`text`,`Testo`,e.text||``)}
        ${k(`image_url`,`URL immagine`,e.image_url||``)}
        ${k(`image_alt`,`Testo alternativo`,e.image_alt||``)}
        ${k(`button_text`,`Testo pulsante`,e.button_text||``)}
        ${k(`button_url`,`URL pulsante`,e.button_url||``)}
        ${j(`background`,`Sfondo`,e.background||`default`,[`default`,`muted`,`dark`,`accent`])}
        ${j(`spacing`,`Spaziatura`,e.spacing||`standard`,[`compact`,`standard`,`wide`])}
        ${j(`alignment`,`Allineamento`,e.alignment||`start`,[`start`,`center`,`end`])}
        ${j(`animation`,`Animazione`,e.animation||`fade-up`,[`fade-up`,`soft-reveal`,`none`])}
        ${k(`style_variant`,`Variante stile`,e.style_variant||`default`)}
      </div>
      <div class="studio-block-visibility mt-3">
        <strong>Visibilit&agrave;</strong>
        ${M(`desktop`,`Desktop`,e)}
        ${M(`tablet`,`Tablet`,e)}
        ${M(`mobile`,`Mobile`,e)}
      </div>
      <div class="studio-block-items mt-3">
        <div class="d-flex justify-content-between align-items-center gap-2 mb-2">
          <strong>Elementi interni</strong>
          <button class="btn btn-sm btn-outline-primary" type="button" data-item-action="add">Aggiungi elemento</button>
        </div>
        <div data-items-list></div>
      </div>
    `,c.querySelectorAll(`[data-prop]`).forEach(e=>{e.addEventListener(`input`,()=>{g[h][e.dataset.prop]=e.type===`checkbox`?e.checked:e.value,e.dataset.visibility&&(g[h].visibility=g[h].visibility||{},g[h].visibility[e.dataset.visibility]=e.checked),v()})});let t=c.querySelector(`[data-item-action='add']`);t&&t.addEventListener(`click`,()=>w()),S()}function S(){let e=c?c.querySelector(`[data-items-list]`):null,t=h>=0?g[h]:null;if(!e||!t)return;let n=Array.isArray(t.items)?t.items:[];e.innerHTML=``,n.forEach((t,n)=>{let r=document.createElement(`div`);r.className=`studio-block-item-editor`,r.innerHTML=`
        ${k(`item-title-${n}`,`Titolo elemento`,t.title||``)}
        ${A(`item-text-${n}`,`Testo elemento`,t.text||``)}
        ${k(`item-image-${n}`,`URL immagine`,t.image_url||``)}
        ${k(`item-alt-${n}`,`Testo alternativo immagine`,t.image_alt||``)}
        ${k(`item-button-${n}`,`Testo pulsante`,t.button_text||``)}
        ${k(`item-url-${n}`,`URL pulsante`,t.button_url||``)}
        <div class="d-flex flex-wrap gap-2">
          <button class="btn btn-sm btn-outline-secondary" type="button" data-item-action="up">Su</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" data-item-action="down">Gi&ugrave;</button>
          <button class="btn btn-sm btn-outline-primary" type="button" data-item-action="duplicate">Duplica</button>
          <button class="btn btn-sm btn-outline-danger" type="button" data-item-action="delete">Elimina</button>
        </div>
      `,C(r,n),e.appendChild(r)}),n.length||(e.innerHTML=`<div class="text-muted small">Questo blocco non ha elementi interni.</div>`)}function C(e,t){[[`item-title`,`title`],[`item-text`,`text`],[`item-image`,`image_url`],[`item-alt`,`image_alt`],[`item-button`,`button_text`],[`item-url`,`button_url`]].forEach(([n,r])=>{let i=e.querySelector(`[data-prop="${n}-${t}"]`);i&&i.addEventListener(`input`,()=>{g[h].items[t][r]=i.value,v()})}),e.querySelectorAll(`[data-item-action]`).forEach(e=>{e.addEventListener(`click`,()=>T(e.dataset.itemAction,t))})}function w(){let e=g[h];e.items=Array.isArray(e.items)?e.items:[],e.items.push({title:`Nuovo elemento`,text:``,image_url:``,image_alt:``}),v(),x()}function T(e,t){let n=g[h].items||[];e===`delete`&&n.splice(t,1),e===`duplicate`&&n.splice(t+1,0,JSON.parse(JSON.stringify(n[t]))),e===`up`&&t>0&&([n[t-1],n[t]]=[n[t],n[t-1]]),e===`down`&&t<n.length-1&&([n[t+1],n[t]]=[n[t],n[t+1]]),v(),x()}async function E(t,n){if(!t||t.endsWith(`/0/blocks`)||t.endsWith(`/0/publish`)){N(`Seleziona una pagina valida prima di salvare.`,`danger`);return}let r=await e(`Salvataggio delle modifiche del sito…`,async()=>(await fetch(t,{method:`POST`,headers:{"Content-Type":`application/json`,Accept:`application/json`},body:JSON.stringify({blocks:g})})).json());N(r.message||r.error||n,r.ok?`success`:`danger`),r.ok&&D()}function D(){if(!i)return;let e=n.dataset.previewUrl||i.src,t=e.includes(`?`)?`&`:`?`;i.src=`${e}${t}_=${Date.now()}`}function O(e){if(!m||!e)return;let t=document.createElement(`button`);t.className=`studio-asset-item`,t.type=`button`,t.dataset.assetUrl=e.url||``,t.dataset.assetAlt=e.alt_text||``,t.innerHTML=`<span>${F(e.title||e.original_filename||`Immagine`)}</span><small>${F(e.alt_text||``)}</small>`,m.prepend(t)}function k(e,t,n,r){return`<label class="form-label">${t}<input class="form-control form-control-sm" data-prop="${e}" value="${P(n)}" ${r?`readonly`:``}></label>`}function A(e,t,n){return`<label class="form-label">${t}<textarea class="form-control form-control-sm" rows="3" data-prop="${e}">${F(n)}</textarea></label>`}function j(e,t,n,r){return`<label class="form-label">${t}<select class="form-select form-select-sm" data-prop="${e}">${r.map(e=>`<option value="${P(e)}" ${e===n?`selected`:``}>${F(e)}</option>`).join(``)}</select></label>`}function M(e,t,n){return`<label class="form-check"><input class="form-check-input" type="checkbox" data-prop="visibility_${e}" data-visibility="${e}" ${!n.visibility||n.visibility[e]!==!1?`checked`:``}> ${t}</label>`}function N(e,t){u&&(u.textContent=e||``,u.className=`studio-builder-status is-${t||`info`}`,window.clearTimeout(N.timer),N.timer=window.setTimeout(()=>{u.textContent=``,u.className=`studio-builder-status`},4200))}function P(e){return String(e||``).replace(/&/g,`&amp;`).replace(/"/g,`&quot;`).replace(/</g,`&lt;`)}function F(e){return String(e||``).replace(/&/g,`&amp;`).replace(/</g,`&lt;`).replace(/>/g,`&gt;`)}y()})();