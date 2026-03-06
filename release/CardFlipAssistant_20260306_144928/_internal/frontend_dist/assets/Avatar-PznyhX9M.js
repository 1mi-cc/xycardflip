import{i as I,o as M}from"./utils-CW5p2vpi.js";import{t as K}from"./Tag-mFSQf70b.js";import{P as N,E as T,aK as W,aL as G,G as E,H as k,k as V,T as A,D as p,aM as D,aN as J,J as U,r as y,S as H,n as O,K as _,aO as X,ax as Y,N as q,aP as Q,o as Z,a3 as ee,a4 as re,s as oe}from"./index-DXgA_KCR.js";const te=N("n-avatar-group"),ne=T("avatar",`
 width: var(--n-merged-size);
 height: var(--n-merged-size);
 color: #FFF;
 font-size: var(--n-font-size);
 display: inline-flex;
 position: relative;
 overflow: hidden;
 text-align: center;
 border: var(--n-border);
 border-radius: var(--n-border-radius);
 --n-merged-color: var(--n-color);
 background-color: var(--n-merged-color);
 transition:
 border-color .3s var(--n-bezier),
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
`,[W(E("&","--n-merged-color: var(--n-color-modal);")),G(E("&","--n-merged-color: var(--n-color-popover);")),E("img",`
 width: 100%;
 height: 100%;
 `),k("text",`
 white-space: nowrap;
 display: inline-block;
 position: absolute;
 left: 50%;
 top: 50%;
 `),T("icon",`
 vertical-align: bottom;
 font-size: calc(var(--n-merged-size) - 6px);
 `),k("text","line-height: 1.25")]),ae=Object.assign(Object.assign({},_.props),{size:[String,Number],src:String,circle:{type:Boolean,default:void 0},objectFit:String,round:{type:Boolean,default:void 0},bordered:{type:Boolean,default:void 0},onError:Function,fallbackSrc:String,intersectionObserverOptions:Object,lazy:Boolean,onLoad:Function,renderPlaceholder:Function,renderFallback:Function,imgProps:Object,color:String}),de=V({name:"Avatar",props:ae,slots:Object,setup(o){const{mergedClsPrefixRef:l,inlineThemeDisabled:m}=U(o),g=y(!1);let d=null;const c=y(null),s=y(null),R=()=>{const{value:e}=c;if(e&&(d===null||d!==e.innerHTML)){d=e.innerHTML;const{value:r}=s;if(r){const{offsetWidth:t,offsetHeight:a}=r,{offsetWidth:n,offsetHeight:P}=e,x=.9,S=Math.min(t/n*x,a/P*x,1);e.style.transform=`translateX(-50%) translateY(-50%) scale(${S})`}}},b=H(te,null),i=O(()=>{const{size:e}=o;if(e)return e;const{size:r}=b||{};return r||"medium"}),u=_("Avatar","-avatar",ne,X,o,l),z=H(K,null),f=O(()=>{if(b)return!0;const{round:e,circle:r}=o;return e!==void 0||r!==void 0?e||r:z?z.roundRef.value:!1}),v=O(()=>b?!0:o.bordered||!1),F=O(()=>{const e=i.value,r=f.value,t=v.value,{color:a}=o,{self:{borderRadius:n,fontSize:P,color:x,border:S,colorModal:w,colorPopover:B},common:{cubicBezierEaseInOut:$}}=u.value;let j;return typeof e=="number"?j=`${e}px`:j=u.value.self[Y("height",e)],{"--n-font-size":P,"--n-border":t?S:"none","--n-border-radius":r?"50%":n,"--n-color":a||x,"--n-color-modal":a||w,"--n-color-popover":a||B,"--n-bezier":$,"--n-merged-size":`var(--n-avatar-size-override, ${j})`}}),h=m?q("avatar",O(()=>{const e=i.value,r=f.value,t=v.value,{color:a}=o;let n="";return e&&(typeof e=="number"?n+=`a${e}`:n+=e[0]),r&&(n+="b"),t&&(n+="c"),a&&(n+=Q(a)),n}),F,o):void 0,L=y(!o.lazy);Z(()=>{if(o.lazy&&o.intersectionObserverOptions){let e;const r=ee(()=>{e==null||e(),e=void 0,o.lazy&&(e=M(s.value,o.intersectionObserverOptions,L))});re(()=>{r(),e==null||e()})}}),oe(()=>{var e;return o.src||((e=o.imgProps)===null||e===void 0?void 0:e.src)},()=>{g.value=!1});const C=y(!o.lazy);return{textRef:c,selfRef:s,mergedRoundRef:f,mergedClsPrefix:l,fitTextTransform:R,cssVars:m?void 0:F,themeClass:h==null?void 0:h.themeClass,onRender:h==null?void 0:h.onRender,hasLoadError:g,shouldStartLoading:L,loaded:C,mergedOnError:e=>{if(!L.value)return;g.value=!0;const{onError:r,imgProps:{onError:t}={}}=o;r==null||r(e),t==null||t(e)},mergedOnLoad:e=>{const{onLoad:r,imgProps:{onLoad:t}={}}=o;r==null||r(e),t==null||t(e),C.value=!0}}},render(){var o,l;const{$slots:m,src:g,mergedClsPrefix:d,lazy:c,onRender:s,loaded:R,hasLoadError:b,imgProps:i={}}=this;s==null||s();let u;const z=!R&&!b&&(this.renderPlaceholder?this.renderPlaceholder():(l=(o=this.$slots).placeholder)===null||l===void 0?void 0:l.call(o));return this.hasLoadError?u=this.renderFallback?this.renderFallback():A(m.fallback,()=>[p("img",{src:this.fallbackSrc,style:{objectFit:this.objectFit}})]):u=D(m.default,f=>{if(f)return p(J,{onResize:this.fitTextTransform},{default:()=>p("span",{ref:"textRef",class:`${d}-avatar__text`},f)});if(g||i.src){const v=this.src||i.src;return p("img",Object.assign(Object.assign({},i),{loading:I&&!this.intersectionObserverOptions&&c?"lazy":"eager",src:c&&this.intersectionObserverOptions?this.shouldStartLoading?v:void 0:v,"data-image-src":v,onLoad:this.mergedOnLoad,onError:this.mergedOnError,style:[i.style||"",{objectFit:this.objectFit},z?{height:"0",width:"0",visibility:"hidden",position:"absolute"}:""]}))}}),p("span",{ref:"selfRef",class:[`${d}-avatar`,this.themeClass],style:this.cssVars},u,c&&z)}});export{de as _};
