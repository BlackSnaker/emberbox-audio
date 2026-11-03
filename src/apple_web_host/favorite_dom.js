/* Idempotent current-song action. Never guess state or toggle another song. */
async function emberboxSetFavorite(find,value,current) {
  function state(control) {
    if(!control||control.disabled)return null;
    for(const key of ['aria-pressed','aria-checked','data-liked','data-checked']) {
      const raw=control.getAttribute(key);
      if(raw==='true')return true;if(raw==='false')return false;
    }
    const label=(control.getAttribute('aria-label')||'')+' '+(control.getAttribute('title')||'');
    if(/remove from.*(library|liked|favou?rites)|удалить.*(медиатек|коллекц|избран|понрав)|больше не нравится/i.test(label))return true;
    if(/add to.*(library|liked|favou?rites)|save to.*library|добавить.*(медиатек|коллекц|избран)|^\s*(like|нравится)\s*$/i.test(label))return false;
    return null;
  }
  if(typeof value!=='boolean'||!await current())throw Error('INVALID_ARGUMENTS');
  const before=state(find());if(before===null)throw Error('ADAPTER_UNAVAILABLE');
  if(before===value)return {favorite:value,confirmed:true};
  find().click();
  for(let n=0;n<16;n++) {
    if(!await current())throw Error('FAVORITE_NOT_CONFIRMED');
    if(state(find())===value)return {favorite:value,confirmed:true};
    await new Promise(resolve=>setTimeout(resolve,125));
  }
  throw Error('FAVORITE_NOT_CONFIRMED');
}
