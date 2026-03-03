import{r as F,n as A,bi as ye,U as ot,k as ce,M as at,D as u,aM as ft,I as rn,aS as St,o as Ne,bV as an,bW as sn,a7 as J,a$ as lt,bp as $e,ap as st,ax as dn,bX as Ze,s as xe,O as Rt,aX as Te,at as un,T as Ft,$ as B,a1 as H,a0 as ie,Y as ue,ag as it,ba as Tt,aL as ht,bo as cn,S as fn,as as hn,K as dt,L as Ot,a6 as Oe,bY as vn,av as we,a_ as Ae,a9 as ut,bZ as gn,F as bn,b_ as pn,N as mn,G as wn,J as yn,P as vt,bl as xn,a5 as Cn,bu as Sn,bt as Rn,b$ as Fn,ab as de}from"./index-BSMS5bAg.js";import{c as Ue,a as Mt,d as Tn,i as ct,f as On,_ as Mn,B as In,V as kn,e as zn,u as rt,b as Pn}from"./Popover-CvqI5pyB.js";import{N as _n}from"./Suffix-BOq3DMxA.js";import{a as Bn,_ as Qe,c as $n}from"./Tag-DoytK_KC.js";import{_ as An}from"./Empty-CjptsqzT.js";import{h as Ee}from"./happens-in-CM8LO42l.js";import{u as gt}from"./use-merged-state-fCj_4uQ6.js";import{u as En}from"./use-locale-DYYn2QyD.js";function bt(e){return e&-e}class It{constructor(n,o){this.l=n,this.min=o;const l=new Array(n+1);for(let i=0;i<n+1;++i)l[i]=0;this.ft=l}add(n,o){if(o===0)return;const{l,ft:i}=this;for(n+=1;n<=l;)i[n]+=o,n+=bt(n)}get(n){return this.sum(n+1)-this.sum(n)}sum(n){if(n===void 0&&(n=this.l),n<=0)return 0;const{ft:o,min:l,l:i}=this;if(n>i)throw new Error("[FinweckTree.sum]: `i` is larger than length.");let f=n*l;for(;n>0;)f+=o[n],n-=bt(n);return f}getBound(n){let o=0,l=this.l;for(;l>o;){const i=Math.floor((o+l)/2),f=this.sum(i);if(f>n){l=i;continue}else if(f<n){if(o===i)return this.sum(o+1)<=n?o+1:i;o=i}else return i}return o}}let Ke;function Nn(){return typeof document>"u"?!1:(Ke===void 0&&("matchMedia"in window?Ke=window.matchMedia("(pointer:coarse)").matches:Ke=!1),Ke)}let et;function pt(){return typeof document>"u"?1:(et===void 0&&(et="chrome"in window?window.devicePixelRatio:1),et)}const kt="VVirtualListXScroll";function Ln({columnsRef:e,renderColRef:n,renderItemWithColsRef:o}){const l=F(0),i=F(0),f=A(()=>{const m=e.value;if(m.length===0)return null;const p=new It(m.length,0);return m.forEach((z,S)=>{p.add(S,z.width)}),p}),v=ye(()=>{const m=f.value;return m!==null?Math.max(m.getBound(i.value)-1,0):0}),a=m=>{const p=f.value;return p!==null?p.sum(m):0},w=ye(()=>{const m=f.value;return m!==null?Math.min(m.getBound(i.value+l.value)+1,e.value.length-1):0});return ot(kt,{startIndexRef:v,endIndexRef:w,columnsRef:e,renderColRef:n,renderItemWithColsRef:o,getLeft:a}),{listWidthRef:l,scrollLeftRef:i}}const mt=ce({name:"VirtualListRow",props:{index:{type:Number,required:!0},item:{type:Object,required:!0}},setup(){const{startIndexRef:e,endIndexRef:n,columnsRef:o,getLeft:l,renderColRef:i,renderItemWithColsRef:f}=at(kt);return{startIndex:e,endIndex:n,columns:o,renderCol:i,renderItemWithCols:f,getLeft:l}},render(){const{startIndex:e,endIndex:n,columns:o,renderCol:l,renderItemWithCols:i,getLeft:f,item:v}=this;if(i!=null)return i({itemIndex:this.index,startColIndex:e,endColIndex:n,allColumns:o,item:v,getLeft:f});if(l!=null){const a=[];for(let w=e;w<=n;++w){const m=o[w];a.push(l({column:m,left:f(w),item:v}))}return a}return null}}),Wn=Ue(".v-vl",{maxHeight:"inherit",height:"100%",overflow:"auto",minWidth:"1px"},[Ue("&:not(.v-vl--show-scrollbar)",{scrollbarWidth:"none"},[Ue("&::-webkit-scrollbar, &::-webkit-scrollbar-track-piece, &::-webkit-scrollbar-thumb",{width:0,height:0,display:"none"})])]),Dn=ce({name:"VirtualList",inheritAttrs:!1,props:{showScrollbar:{type:Boolean,default:!0},columns:{type:Array,default:()=>[]},renderCol:Function,renderItemWithCols:Function,items:{type:Array,default:()=>[]},itemSize:{type:Number,required:!0},itemResizable:Boolean,itemsStyle:[String,Object],visibleItemsTag:{type:[String,Object],default:"div"},visibleItemsProps:Object,ignoreItemResize:Boolean,onScroll:Function,onWheel:Function,onResize:Function,defaultScrollKey:[Number,String],defaultScrollIndex:Number,keyField:{type:String,default:"key"},paddingTop:{type:[Number,String],default:0},paddingBottom:{type:[Number,String],default:0}},setup(e){const n=St();Wn.mount({id:"vueuc/virtual-list",head:!0,anchorMetaName:Mt,ssr:n}),Ne(()=>{const{defaultScrollIndex:s,defaultScrollKey:b}=e;s!=null?K({index:s}):b!=null&&K({key:b})});let o=!1,l=!1;an(()=>{if(o=!1,!l){l=!0;return}K({top:C.value,left:v.value})}),sn(()=>{o=!0,l||(l=!0)});const i=ye(()=>{if(e.renderCol==null&&e.renderItemWithCols==null||e.columns.length===0)return;let s=0;return e.columns.forEach(b=>{s+=b.width}),s}),f=A(()=>{const s=new Map,{keyField:b}=e;return e.items.forEach((P,D)=>{s.set(P[b],D)}),s}),{scrollLeftRef:v,listWidthRef:a}=Ln({columnsRef:J(e,"columns"),renderColRef:J(e,"renderCol"),renderItemWithColsRef:J(e,"renderItemWithCols")}),w=F(null),m=F(void 0),p=new Map,z=A(()=>{const{items:s,itemSize:b,keyField:P}=e,D=new It(s.length,b);return s.forEach((q,V)=>{const j=q[P],E=p.get(j);E!==void 0&&D.add(V,E)}),D}),S=F(0),C=F(0),y=ye(()=>Math.max(z.value.getBound(C.value-lt(e.paddingTop))-1,0)),L=A(()=>{const{value:s}=m;if(s===void 0)return[];const{items:b,itemSize:P}=e,D=y.value,q=Math.min(D+Math.ceil(s/P+1),b.length-1),V=[];for(let j=D;j<=q;++j)V.push(b[j]);return V}),K=(s,b)=>{if(typeof s=="number"){$(s,b,"auto");return}const{left:P,top:D,index:q,key:V,position:j,behavior:E,debounce:X=!0}=s;if(P!==void 0||D!==void 0)$(P,D,E);else if(q!==void 0)T(q,E,X);else if(V!==void 0){const d=f.value.get(V);d!==void 0&&T(d,E,X)}else j==="bottom"?$(0,Number.MAX_SAFE_INTEGER,E):j==="top"&&$(0,0,E)};let O,R=null;function T(s,b,P){const{value:D}=z,q=D.sum(s)+lt(e.paddingTop);if(!P)w.value.scrollTo({left:0,top:q,behavior:b});else{O=s,R!==null&&window.clearTimeout(R),R=window.setTimeout(()=>{O=void 0,R=null},16);const{scrollTop:V,offsetHeight:j}=w.value;if(q>V){const E=D.get(s);q+E<=V+j||w.value.scrollTo({left:0,top:q+E-j,behavior:b})}else w.value.scrollTo({left:0,top:q,behavior:b})}}function $(s,b,P){w.value.scrollTo({left:s,top:b,behavior:P})}function W(s,b){var P,D,q;if(o||e.ignoreItemResize||ae(b.target))return;const{value:V}=z,j=f.value.get(s),E=V.get(j),X=(q=(D=(P=b.borderBoxSize)===null||P===void 0?void 0:P[0])===null||D===void 0?void 0:D.blockSize)!==null&&q!==void 0?q:b.contentRect.height;if(X===E)return;X-e.itemSize===0?p.delete(s):p.set(s,X-e.itemSize);const h=X-E;if(h===0)return;V.add(j,h);const N=w.value;if(N!=null){if(O===void 0){const oe=V.sum(j);N.scrollTop>oe&&N.scrollBy(0,h)}else if(j<O)N.scrollBy(0,h);else if(j===O){const oe=V.sum(j);X+oe>N.scrollTop+N.offsetHeight&&N.scrollBy(0,h)}te()}S.value++}const Z=!Nn();let U=!1;function ne(s){var b;(b=e.onScroll)===null||b===void 0||b.call(e,s),(!Z||!U)&&te()}function re(s){var b;if((b=e.onWheel)===null||b===void 0||b.call(e,s),Z){const P=w.value;if(P!=null){if(s.deltaX===0&&(P.scrollTop===0&&s.deltaY<=0||P.scrollTop+P.offsetHeight>=P.scrollHeight&&s.deltaY>=0))return;s.preventDefault(),P.scrollTop+=s.deltaY/pt(),P.scrollLeft+=s.deltaX/pt(),te(),U=!0,Tn(()=>{U=!1})}}}function Q(s){if(o||ae(s.target))return;if(e.renderCol==null&&e.renderItemWithCols==null){if(s.contentRect.height===m.value)return}else if(s.contentRect.height===m.value&&s.contentRect.width===a.value)return;m.value=s.contentRect.height,a.value=s.contentRect.width;const{onResize:b}=e;b!==void 0&&b(s)}function te(){const{value:s}=w;s!=null&&(C.value=s.scrollTop,v.value=s.scrollLeft)}function ae(s){let b=s;for(;b!==null;){if(b.style.display==="none")return!0;b=b.parentElement}return!1}return{listHeight:m,listStyle:{overflow:"auto"},keyToIndex:f,itemsStyle:A(()=>{const{itemResizable:s}=e,b=$e(z.value.sum());return S.value,[e.itemsStyle,{boxSizing:"content-box",width:$e(i.value),height:s?"":b,minHeight:s?b:"",paddingTop:$e(e.paddingTop),paddingBottom:$e(e.paddingBottom)}]}),visibleItemsStyle:A(()=>(S.value,{transform:`translateY(${$e(z.value.sum(y.value))})`})),viewportItems:L,listElRef:w,itemsElRef:F(null),scrollTo:K,handleListResize:Q,handleListScroll:ne,handleListWheel:re,handleItemResize:W}},render(){const{itemResizable:e,keyField:n,keyToIndex:o,visibleItemsTag:l}=this;return u(ft,{onResize:this.handleListResize},{default:()=>{var i,f;return u("div",rn(this.$attrs,{class:["v-vl",this.showScrollbar&&"v-vl--show-scrollbar"],onScroll:this.handleListScroll,onWheel:this.handleListWheel,ref:"listElRef"}),[this.items.length!==0?u("div",{ref:"itemsElRef",class:"v-vl-items",style:this.itemsStyle},[u(l,Object.assign({class:"v-vl-visible-items",style:this.visibleItemsStyle},this.visibleItemsProps),{default:()=>{const{renderCol:v,renderItemWithCols:a}=this;return this.viewportItems.map(w=>{const m=w[n],p=o.get(m),z=v!=null?u(mt,{index:p,item:w}):void 0,S=a!=null?u(mt,{index:p,item:w}):void 0,C=this.$slots.default({item:w,renderedCols:z,renderedItemWithCols:S,index:p})[0];return e?u(ft,{key:m,onResize:y=>this.handleItemResize(m,y)},{default:()=>C}):(C.key=m,C)})}})]):(f=(i=this.$slots).empty)===null||f===void 0?void 0:f.call(i)])}})}}),he="v-hidden",Vn=Ue("[v-hidden]",{display:"none!important"}),wt=ce({name:"Overflow",props:{getCounter:Function,getTail:Function,updateCounter:Function,onUpdateCount:Function,onUpdateOverflow:Function},setup(e,{slots:n}){const o=F(null),l=F(null);function i(v){const{value:a}=o,{getCounter:w,getTail:m}=e;let p;if(w!==void 0?p=w():p=l.value,!a||!p)return;p.hasAttribute(he)&&p.removeAttribute(he);const{children:z}=a;if(v.showAllItemsBeforeCalculate)for(const T of z)T.hasAttribute(he)&&T.removeAttribute(he);const S=a.offsetWidth,C=[],y=n.tail?m==null?void 0:m():null;let L=y?y.offsetWidth:0,K=!1;const O=a.children.length-(n.tail?1:0);for(let T=0;T<O-1;++T){if(T<0)continue;const $=z[T];if(K){$.hasAttribute(he)||$.setAttribute(he,"");continue}else $.hasAttribute(he)&&$.removeAttribute(he);const W=$.offsetWidth;if(L+=W,C[T]=W,L>S){const{updateCounter:Z}=e;for(let U=T;U>=0;--U){const ne=O-1-U;Z!==void 0?Z(ne):p.textContent=`${ne}`;const re=p.offsetWidth;if(L-=C[U],L+re<=S||U===0){K=!0,T=U-1,y&&(T===-1?(y.style.maxWidth=`${S-re}px`,y.style.boxSizing="border-box"):y.style.maxWidth="");const{onUpdateCount:Q}=e;Q&&Q(ne);break}}}}const{onUpdateOverflow:R}=e;K?R!==void 0&&R(!0):(R!==void 0&&R(!1),p.setAttribute(he,""))}const f=St();return Vn.mount({id:"vueuc/overflow",head:!0,anchorMetaName:Mt,ssr:f}),Ne(()=>i({showAllItemsBeforeCalculate:!1})),{selfRef:o,counterRef:l,sync:i}},render(){const{$slots:e}=this;return st(()=>this.sync({showAllItemsBeforeCalculate:!1})),u("div",{class:"v-overflow",ref:"selfRef"},[dn(e,"default"),e.counter?e.counter():u("span",{style:{display:"inline-block"},ref:"counterRef"}),e.tail?e.tail():null])}});function zt(e,n){n&&(Ne(()=>{const{value:o}=e;o&&Ze.registerHandler(o,n)}),xe(e,(o,l)=>{l&&Ze.unregisterHandler(l)},{deep:!1}),Rt(()=>{const{value:o}=e;o&&Ze.unregisterHandler(o)}))}function yt(e){switch(typeof e){case"string":return e||void 0;case"number":return String(e);default:return}}function tt(e){const n=e.filter(o=>o!==void 0);if(n.length!==0)return n.length===1?n[0]:o=>{e.forEach(l=>{l&&l(o)})}}const jn=ce({name:"Checkmark",render(){return u("svg",{xmlns:"http://www.w3.org/2000/svg",viewBox:"0 0 16 16"},u("g",{fill:"none"},u("path",{d:"M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032z",fill:"currentColor"})))}}),Hn=ce({props:{onFocus:Function,onBlur:Function},setup(e){return()=>u("div",{style:"width: 0; height: 0",tabindex:0,onFocus:e.onFocus,onBlur:e.onBlur})}}),xt=ce({name:"NBaseSelectGroupHeader",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){const{renderLabelRef:e,renderOptionRef:n,labelFieldRef:o,nodePropsRef:l}=at(ct);return{labelField:o,nodeProps:l,renderLabel:e,renderOption:n}},render(){const{clsPrefix:e,renderLabel:n,renderOption:o,nodeProps:l,tmNode:{rawNode:i}}=this,f=l==null?void 0:l(i),v=n?n(i,!1):Te(i[this.labelField],i,!1),a=u("div",Object.assign({},f,{class:[`${e}-base-select-group-header`,f==null?void 0:f.class]}),v);return i.render?i.render({node:a,option:i}):o?o({node:a,option:i,selected:!1}):a}});function Kn(e,n){return u(Ft,{name:"fade-in-scale-up-transition"},{default:()=>e?u(un,{clsPrefix:n,class:`${n}-base-select-option__check`},{default:()=>u(jn)}):null})}const Ct=ce({name:"NBaseSelectOption",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(e){const{valueRef:n,pendingTmNodeRef:o,multipleRef:l,valueSetRef:i,renderLabelRef:f,renderOptionRef:v,labelFieldRef:a,valueFieldRef:w,showCheckmarkRef:m,nodePropsRef:p,handleOptionClick:z,handleOptionMouseEnter:S}=at(ct),C=ye(()=>{const{value:O}=o;return O?e.tmNode.key===O.key:!1});function y(O){const{tmNode:R}=e;R.disabled||z(O,R)}function L(O){const{tmNode:R}=e;R.disabled||S(O,R)}function K(O){const{tmNode:R}=e,{value:T}=C;R.disabled||T||S(O,R)}return{multiple:l,isGrouped:ye(()=>{const{tmNode:O}=e,{parent:R}=O;return R&&R.rawNode.type==="group"}),showCheckmark:m,nodeProps:p,isPending:C,isSelected:ye(()=>{const{value:O}=n,{value:R}=l;if(O===null)return!1;const T=e.tmNode.rawNode[w.value];if(R){const{value:$}=i;return $.has(T)}else return O===T}),labelField:a,renderLabel:f,renderOption:v,handleMouseMove:K,handleMouseEnter:L,handleClick:y}},render(){const{clsPrefix:e,tmNode:{rawNode:n},isSelected:o,isPending:l,isGrouped:i,showCheckmark:f,nodeProps:v,renderOption:a,renderLabel:w,handleClick:m,handleMouseEnter:p,handleMouseMove:z}=this,S=Kn(o,e),C=w?[w(n,o),f&&S]:[Te(n[this.labelField],n,o),f&&S],y=v==null?void 0:v(n),L=u("div",Object.assign({},y,{class:[`${e}-base-select-option`,n.class,y==null?void 0:y.class,{[`${e}-base-select-option--disabled`]:n.disabled,[`${e}-base-select-option--selected`]:o,[`${e}-base-select-option--grouped`]:i,[`${e}-base-select-option--pending`]:l,[`${e}-base-select-option--show-checkmark`]:f}],style:[(y==null?void 0:y.style)||"",n.style||""],onClick:tt([m,y==null?void 0:y.onClick]),onMouseenter:tt([p,y==null?void 0:y.onMouseenter]),onMousemove:tt([z,y==null?void 0:y.onMousemove])}),u("div",{class:`${e}-base-select-option__content`},C));return n.render?n.render({node:L,option:n,selected:o}):a?a({node:L,option:n,selected:o}):L}}),Un=B("base-select-menu",`
 line-height: 1.5;
 outline: none;
 z-index: 0;
 position: relative;
 border-radius: var(--n-border-radius);
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
 background-color: var(--n-color);
`,[B("scrollbar",`
 max-height: var(--n-height);
 `),B("virtual-list",`
 max-height: var(--n-height);
 `),B("base-select-option",`
 min-height: var(--n-option-height);
 font-size: var(--n-option-font-size);
 display: flex;
 align-items: center;
 `,[H("content",`
 z-index: 1;
 white-space: nowrap;
 text-overflow: ellipsis;
 overflow: hidden;
 `)]),B("base-select-group-header",`
 min-height: var(--n-option-height);
 font-size: .93em;
 display: flex;
 align-items: center;
 `),B("base-select-menu-option-wrapper",`
 position: relative;
 width: 100%;
 `),H("loading, empty",`
 display: flex;
 padding: 12px 32px;
 flex: 1;
 justify-content: center;
 `),H("loading",`
 color: var(--n-loading-color);
 font-size: var(--n-loading-size);
 `),H("header",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),H("action",`
 padding: 8px var(--n-option-padding-left);
 font-size: var(--n-option-font-size);
 transition: 
 color .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 border-top: 1px solid var(--n-action-divider-color);
 color: var(--n-action-text-color);
 `),B("base-select-group-header",`
 position: relative;
 cursor: default;
 padding: var(--n-option-padding);
 color: var(--n-group-header-text-color);
 `),B("base-select-option",`
 cursor: pointer;
 position: relative;
 padding: var(--n-option-padding);
 transition:
 color .3s var(--n-bezier),
 opacity .3s var(--n-bezier);
 box-sizing: border-box;
 color: var(--n-option-text-color);
 opacity: 1;
 `,[ie("show-checkmark",`
 padding-right: calc(var(--n-option-padding-right) + 20px);
 `),ue("&::before",`
 content: "";
 position: absolute;
 left: 4px;
 right: 4px;
 top: 0;
 bottom: 0;
 border-radius: var(--n-border-radius);
 transition: background-color .3s var(--n-bezier);
 `),ue("&:active",`
 color: var(--n-option-text-color-pressed);
 `),ie("grouped",`
 padding-left: calc(var(--n-option-padding-left) * 1.5);
 `),ie("pending",[ue("&::before",`
 background-color: var(--n-option-color-pending);
 `)]),ie("selected",`
 color: var(--n-option-text-color-active);
 `,[ue("&::before",`
 background-color: var(--n-option-color-active);
 `),ie("pending",[ue("&::before",`
 background-color: var(--n-option-color-active-pending);
 `)])]),ie("disabled",`
 cursor: not-allowed;
 `,[it("selected",`
 color: var(--n-option-text-color-disabled);
 `),ie("selected",`
 opacity: var(--n-option-opacity-disabled);
 `)]),H("check",`
 font-size: 16px;
 position: absolute;
 right: calc(var(--n-option-padding-right) - 4px);
 top: calc(50% - 7px);
 color: var(--n-option-check-color);
 transition: color .3s var(--n-bezier);
 `,[Tt({enterScale:"0.5"})])])]),qn=ce({name:"InternalSelectMenu",props:Object.assign(Object.assign({},Oe.props),{clsPrefix:{type:String,required:!0},scrollable:{type:Boolean,default:!0},treeMate:{type:Object,required:!0},multiple:Boolean,size:{type:String,default:"medium"},value:{type:[String,Number,Array],default:null},autoPending:Boolean,virtualScroll:{type:Boolean,default:!0},show:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},loading:Boolean,focusable:Boolean,renderLabel:Function,renderOption:Function,nodeProps:Function,showCheckmark:{type:Boolean,default:!0},onMousedown:Function,onScroll:Function,onFocus:Function,onBlur:Function,onKeyup:Function,onKeydown:Function,onTabOut:Function,onMouseenter:Function,onMouseleave:Function,onResize:Function,resetMenuOnOptionsChange:{type:Boolean,default:!0},inlineThemeDisabled:Boolean,onToggle:Function}),setup(e){const{mergedClsPrefixRef:n,mergedRtlRef:o}=dt(e),l=Ot("InternalSelectMenu",o,n),i=Oe("InternalSelectMenu","-internal-select-menu",Un,vn,e,J(e,"clsPrefix")),f=F(null),v=F(null),a=F(null),w=A(()=>e.treeMate.getFlattenedNodes()),m=A(()=>Bn(w.value)),p=F(null);function z(){const{treeMate:d}=e;let h=null;const{value:N}=e;N===null?h=d.getFirstAvailableNode():(e.multiple?h=d.getNode((N||[])[(N||[]).length-1]):h=d.getNode(N),(!h||h.disabled)&&(h=d.getFirstAvailableNode())),b(h||null)}function S(){const{value:d}=p;d&&!e.treeMate.getNode(d.key)&&(p.value=null)}let C;xe(()=>e.show,d=>{d?C=xe(()=>e.treeMate,()=>{e.resetMenuOnOptionsChange?(e.autoPending?z():S(),st(P)):S()},{immediate:!0}):C==null||C()},{immediate:!0}),Rt(()=>{C==null||C()});const y=A(()=>lt(i.value.self[we("optionHeight",e.size)])),L=A(()=>Ae(i.value.self[we("padding",e.size)])),K=A(()=>e.multiple&&Array.isArray(e.value)?new Set(e.value):new Set),O=A(()=>{const d=w.value;return d&&d.length===0});function R(d){const{onToggle:h}=e;h&&h(d)}function T(d){const{onScroll:h}=e;h&&h(d)}function $(d){var h;(h=a.value)===null||h===void 0||h.sync(),T(d)}function W(){var d;(d=a.value)===null||d===void 0||d.sync()}function Z(){const{value:d}=p;return d||null}function U(d,h){h.disabled||b(h,!1)}function ne(d,h){h.disabled||R(h)}function re(d){var h;Ee(d,"action")||(h=e.onKeyup)===null||h===void 0||h.call(e,d)}function Q(d){var h;Ee(d,"action")||(h=e.onKeydown)===null||h===void 0||h.call(e,d)}function te(d){var h;(h=e.onMousedown)===null||h===void 0||h.call(e,d),!e.focusable&&d.preventDefault()}function ae(){const{value:d}=p;d&&b(d.getNext({loop:!0}),!0)}function s(){const{value:d}=p;d&&b(d.getPrev({loop:!0}),!0)}function b(d,h=!1){p.value=d,h&&P()}function P(){var d,h;const N=p.value;if(!N)return;const oe=m.value(N.key);oe!==null&&(e.virtualScroll?(d=v.value)===null||d===void 0||d.scrollTo({index:oe}):(h=a.value)===null||h===void 0||h.scrollTo({index:oe,elSize:y.value}))}function D(d){var h,N;!((h=f.value)===null||h===void 0)&&h.contains(d.target)&&((N=e.onFocus)===null||N===void 0||N.call(e,d))}function q(d){var h,N;!((h=f.value)===null||h===void 0)&&h.contains(d.relatedTarget)||(N=e.onBlur)===null||N===void 0||N.call(e,d)}ot(ct,{handleOptionMouseEnter:U,handleOptionClick:ne,valueSetRef:K,pendingTmNodeRef:p,nodePropsRef:J(e,"nodeProps"),showCheckmarkRef:J(e,"showCheckmark"),multipleRef:J(e,"multiple"),valueRef:J(e,"value"),renderLabelRef:J(e,"renderLabel"),renderOptionRef:J(e,"renderOption"),labelFieldRef:J(e,"labelField"),valueFieldRef:J(e,"valueField")}),ot(On,f),Ne(()=>{const{value:d}=a;d&&d.sync()});const V=A(()=>{const{size:d}=e,{common:{cubicBezierEaseInOut:h},self:{height:N,borderRadius:oe,color:Ce,groupHeaderTextColor:Se,actionDividerColor:fe,optionTextColorPressed:le,optionTextColor:Re,optionTextColorDisabled:ve,optionTextColorActive:Me,optionOpacityDisabled:Ie,optionCheckColor:ke,actionTextColor:ze,optionColorPending:be,optionColorActive:pe,loadingColor:Pe,loadingSize:_e,optionColorActivePending:Be,[we("optionFontSize",d)]:Fe,[we("optionHeight",d)]:me,[we("optionPadding",d)]:ee}}=i.value;return{"--n-height":N,"--n-action-divider-color":fe,"--n-action-text-color":ze,"--n-bezier":h,"--n-border-radius":oe,"--n-color":Ce,"--n-option-font-size":Fe,"--n-group-header-text-color":Se,"--n-option-check-color":ke,"--n-option-color-pending":be,"--n-option-color-active":pe,"--n-option-color-active-pending":Be,"--n-option-height":me,"--n-option-opacity-disabled":Ie,"--n-option-text-color":Re,"--n-option-text-color-active":Me,"--n-option-text-color-disabled":ve,"--n-option-text-color-pressed":le,"--n-option-padding":ee,"--n-option-padding-left":Ae(ee,"left"),"--n-option-padding-right":Ae(ee,"right"),"--n-loading-color":Pe,"--n-loading-size":_e}}),{inlineThemeDisabled:j}=e,E=j?ut("internal-select-menu",A(()=>e.size[0]),V,e):void 0,X={selfRef:f,next:ae,prev:s,getPendingTmNode:Z};return zt(f,e.onResize),Object.assign({mergedTheme:i,mergedClsPrefix:n,rtlEnabled:l,virtualListRef:v,scrollbarRef:a,itemSize:y,padding:L,flattenedNodes:w,empty:O,virtualListContainer(){const{value:d}=v;return d==null?void 0:d.listElRef},virtualListContent(){const{value:d}=v;return d==null?void 0:d.itemsElRef},doScroll:T,handleFocusin:D,handleFocusout:q,handleKeyUp:re,handleKeyDown:Q,handleMouseDown:te,handleVirtualListResize:W,handleVirtualListScroll:$,cssVars:j?void 0:V,themeClass:E==null?void 0:E.themeClass,onRender:E==null?void 0:E.onRender},X)},render(){const{$slots:e,virtualScroll:n,clsPrefix:o,mergedTheme:l,themeClass:i,onRender:f}=this;return f==null||f(),u("div",{ref:"selfRef",tabindex:this.focusable?0:-1,class:[`${o}-base-select-menu`,this.rtlEnabled&&`${o}-base-select-menu--rtl`,i,this.multiple&&`${o}-base-select-menu--multiple`],style:this.cssVars,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onKeyup:this.handleKeyUp,onKeydown:this.handleKeyDown,onMousedown:this.handleMouseDown,onMouseenter:this.onMouseenter,onMouseleave:this.onMouseleave},ht(e.header,v=>v&&u("div",{class:`${o}-base-select-menu__header`,"data-header":!0,key:"header"},v)),this.loading?u("div",{class:`${o}-base-select-menu__loading`},u(cn,{clsPrefix:o,strokeWidth:20})):this.empty?u("div",{class:`${o}-base-select-menu__empty`,"data-empty":!0},hn(e.empty,()=>[u(An,{theme:l.peers.Empty,themeOverrides:l.peerOverrides.Empty,size:this.size})])):u(fn,{ref:"scrollbarRef",theme:l.peers.Scrollbar,themeOverrides:l.peerOverrides.Scrollbar,scrollable:this.scrollable,container:n?this.virtualListContainer:void 0,content:n?this.virtualListContent:void 0,onScroll:n?void 0:this.doScroll},{default:()=>n?u(Dn,{ref:"virtualListRef",class:`${o}-virtual-list`,items:this.flattenedNodes,itemSize:this.itemSize,showScrollbar:!1,paddingTop:this.padding.top,paddingBottom:this.padding.bottom,onResize:this.handleVirtualListResize,onScroll:this.handleVirtualListScroll,itemResizable:!0},{default:({item:v})=>v.isGroup?u(xt,{key:v.key,clsPrefix:o,tmNode:v}):v.ignored?null:u(Ct,{clsPrefix:o,key:v.key,tmNode:v})}):u("div",{class:`${o}-base-select-menu-option-wrapper`,style:{paddingTop:this.padding.top,paddingBottom:this.padding.bottom}},this.flattenedNodes.map(v=>v.isGroup?u(xt,{key:v.key,clsPrefix:o,tmNode:v}):u(Ct,{clsPrefix:o,key:v.key,tmNode:v})))}),ht(e.action,v=>v&&[u("div",{class:`${o}-base-select-menu__action`,"data-action":!0,key:"action"},v),u(Hn,{onFocus:this.onTabOut,key:"focus-detector"})]))}}),Gn=ue([B("base-selection",`
 --n-padding-single: var(--n-padding-single-top) var(--n-padding-single-right) var(--n-padding-single-bottom) var(--n-padding-single-left);
 --n-padding-multiple: var(--n-padding-multiple-top) var(--n-padding-multiple-right) var(--n-padding-multiple-bottom) var(--n-padding-multiple-left);
 position: relative;
 z-index: auto;
 box-shadow: none;
 width: 100%;
 max-width: 100%;
 display: inline-block;
 vertical-align: bottom;
 border-radius: var(--n-border-radius);
 min-height: var(--n-height);
 line-height: 1.5;
 font-size: var(--n-font-size);
 `,[B("base-loading",`
 color: var(--n-loading-color);
 `),B("base-selection-tags","min-height: var(--n-height);"),H("border, state-border",`
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 border: var(--n-border);
 border-radius: inherit;
 transition:
 box-shadow .3s var(--n-bezier),
 border-color .3s var(--n-bezier);
 `),H("state-border",`
 z-index: 1;
 border-color: #0000;
 `),B("base-suffix",`
 cursor: pointer;
 position: absolute;
 top: 50%;
 transform: translateY(-50%);
 right: 10px;
 `,[H("arrow",`
 font-size: var(--n-arrow-size);
 color: var(--n-arrow-color);
 transition: color .3s var(--n-bezier);
 `)]),B("base-selection-overlay",`
 display: flex;
 align-items: center;
 white-space: nowrap;
 pointer-events: none;
 position: absolute;
 top: 0;
 right: 0;
 bottom: 0;
 left: 0;
 padding: var(--n-padding-single);
 transition: color .3s var(--n-bezier);
 `,[H("wrapper",`
 flex-basis: 0;
 flex-grow: 1;
 overflow: hidden;
 text-overflow: ellipsis;
 `)]),B("base-selection-placeholder",`
 color: var(--n-placeholder-color);
 `,[H("inner",`
 max-width: 100%;
 overflow: hidden;
 `)]),B("base-selection-tags",`
 cursor: pointer;
 outline: none;
 box-sizing: border-box;
 position: relative;
 z-index: auto;
 display: flex;
 padding: var(--n-padding-multiple);
 flex-wrap: wrap;
 align-items: center;
 width: 100%;
 vertical-align: bottom;
 background-color: var(--n-color);
 border-radius: inherit;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 `),B("base-selection-label",`
 height: var(--n-height);
 display: inline-flex;
 width: 100%;
 vertical-align: bottom;
 cursor: pointer;
 outline: none;
 z-index: auto;
 box-sizing: border-box;
 position: relative;
 transition:
 color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier),
 background-color .3s var(--n-bezier);
 border-radius: inherit;
 background-color: var(--n-color);
 align-items: center;
 `,[B("base-selection-input",`
 font-size: inherit;
 line-height: inherit;
 outline: none;
 cursor: pointer;
 box-sizing: border-box;
 border:none;
 width: 100%;
 padding: var(--n-padding-single);
 background-color: #0000;
 color: var(--n-text-color);
 transition: color .3s var(--n-bezier);
 caret-color: var(--n-caret-color);
 `,[H("content",`
 text-overflow: ellipsis;
 overflow: hidden;
 white-space: nowrap; 
 `)]),H("render-label",`
 color: var(--n-text-color);
 `)]),it("disabled",[ue("&:hover",[H("state-border",`
 box-shadow: var(--n-box-shadow-hover);
 border: var(--n-border-hover);
 `)]),ie("focus",[H("state-border",`
 box-shadow: var(--n-box-shadow-focus);
 border: var(--n-border-focus);
 `)]),ie("active",[H("state-border",`
 box-shadow: var(--n-box-shadow-active);
 border: var(--n-border-active);
 `),B("base-selection-label","background-color: var(--n-color-active);"),B("base-selection-tags","background-color: var(--n-color-active);")])]),ie("disabled","cursor: not-allowed;",[H("arrow",`
 color: var(--n-arrow-color-disabled);
 `),B("base-selection-label",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `,[B("base-selection-input",`
 cursor: not-allowed;
 color: var(--n-text-color-disabled);
 `),H("render-label",`
 color: var(--n-text-color-disabled);
 `)]),B("base-selection-tags",`
 cursor: not-allowed;
 background-color: var(--n-color-disabled);
 `),B("base-selection-placeholder",`
 cursor: not-allowed;
 color: var(--n-placeholder-color-disabled);
 `)]),B("base-selection-input-tag",`
 height: calc(var(--n-height) - 6px);
 line-height: calc(var(--n-height) - 6px);
 outline: none;
 display: none;
 position: relative;
 margin-bottom: 3px;
 max-width: 100%;
 vertical-align: bottom;
 `,[H("input",`
 font-size: inherit;
 font-family: inherit;
 min-width: 1px;
 padding: 0;
 background-color: #0000;
 outline: none;
 border: none;
 max-width: 100%;
 overflow: hidden;
 width: 1em;
 line-height: inherit;
 cursor: pointer;
 color: var(--n-text-color);
 caret-color: var(--n-caret-color);
 `),H("mirror",`
 position: absolute;
 left: 0;
 top: 0;
 white-space: pre;
 visibility: hidden;
 user-select: none;
 -webkit-user-select: none;
 opacity: 0;
 `)]),["warning","error"].map(e=>ie(`${e}-status`,[H("state-border",`border: var(--n-border-${e});`),it("disabled",[ue("&:hover",[H("state-border",`
 box-shadow: var(--n-box-shadow-hover-${e});
 border: var(--n-border-hover-${e});
 `)]),ie("active",[H("state-border",`
 box-shadow: var(--n-box-shadow-active-${e});
 border: var(--n-border-active-${e});
 `),B("base-selection-label",`background-color: var(--n-color-active-${e});`),B("base-selection-tags",`background-color: var(--n-color-active-${e});`)]),ie("focus",[H("state-border",`
 box-shadow: var(--n-box-shadow-focus-${e});
 border: var(--n-border-focus-${e});
 `)])])]))]),B("base-selection-popover",`
 margin-bottom: -3px;
 display: flex;
 flex-wrap: wrap;
 margin-right: -8px;
 `),B("base-selection-tag-wrapper",`
 max-width: 100%;
 display: inline-flex;
 padding: 0 7px 3px 0;
 `,[ue("&:last-child","padding-right: 0;"),B("tag",`
 font-size: 14px;
 max-width: 100%;
 `,[H("content",`
 line-height: 1.25;
 text-overflow: ellipsis;
 overflow: hidden;
 `)])])]),Xn=ce({name:"InternalSelection",props:Object.assign(Object.assign({},Oe.props),{clsPrefix:{type:String,required:!0},bordered:{type:Boolean,default:void 0},active:Boolean,pattern:{type:String,default:""},placeholder:String,selectedOption:{type:Object,default:null},selectedOptions:{type:Array,default:null},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},multiple:Boolean,filterable:Boolean,clearable:Boolean,disabled:Boolean,size:{type:String,default:"medium"},loading:Boolean,autofocus:Boolean,showArrow:{type:Boolean,default:!0},inputProps:Object,focused:Boolean,renderTag:Function,onKeydown:Function,onClick:Function,onBlur:Function,onFocus:Function,onDeleteOption:Function,maxTagCount:[String,Number],ellipsisTagPopoverProps:Object,onClear:Function,onPatternInput:Function,onPatternFocus:Function,onPatternBlur:Function,renderLabel:Function,status:String,inlineThemeDisabled:Boolean,ignoreComposition:{type:Boolean,default:!0},onResize:Function}),setup(e){const{mergedClsPrefixRef:n,mergedRtlRef:o}=dt(e),l=Ot("InternalSelection",o,n),i=F(null),f=F(null),v=F(null),a=F(null),w=F(null),m=F(null),p=F(null),z=F(null),S=F(null),C=F(null),y=F(!1),L=F(!1),K=F(!1),O=Oe("InternalSelection","-internal-selection",Gn,pn,e,J(e,"clsPrefix")),R=A(()=>e.clearable&&!e.disabled&&(K.value||e.active)),T=A(()=>e.selectedOption?e.renderTag?e.renderTag({option:e.selectedOption,handleClose:()=>{}}):e.renderLabel?e.renderLabel(e.selectedOption,!0):Te(e.selectedOption[e.labelField],e.selectedOption,!0):e.placeholder),$=A(()=>{const r=e.selectedOption;if(r)return r[e.labelField]}),W=A(()=>e.multiple?!!(Array.isArray(e.selectedOptions)&&e.selectedOptions.length):e.selectedOption!==null);function Z(){var r;const{value:g}=i;if(g){const{value:G}=f;G&&(G.style.width=`${g.offsetWidth}px`,e.maxTagCount!=="responsive"&&((r=S.value)===null||r===void 0||r.sync({showAllItemsBeforeCalculate:!1})))}}function U(){const{value:r}=C;r&&(r.style.display="none")}function ne(){const{value:r}=C;r&&(r.style.display="inline-block")}xe(J(e,"active"),r=>{r||U()}),xe(J(e,"pattern"),()=>{e.multiple&&st(Z)});function re(r){const{onFocus:g}=e;g&&g(r)}function Q(r){const{onBlur:g}=e;g&&g(r)}function te(r){const{onDeleteOption:g}=e;g&&g(r)}function ae(r){const{onClear:g}=e;g&&g(r)}function s(r){const{onPatternInput:g}=e;g&&g(r)}function b(r){var g;(!r.relatedTarget||!(!((g=v.value)===null||g===void 0)&&g.contains(r.relatedTarget)))&&re(r)}function P(r){var g;!((g=v.value)===null||g===void 0)&&g.contains(r.relatedTarget)||Q(r)}function D(r){ae(r)}function q(){K.value=!0}function V(){K.value=!1}function j(r){!e.active||!e.filterable||r.target!==f.value&&r.preventDefault()}function E(r){te(r)}const X=F(!1);function d(r){if(r.key==="Backspace"&&!X.value&&!e.pattern.length){const{selectedOptions:g}=e;g!=null&&g.length&&E(g[g.length-1])}}let h=null;function N(r){const{value:g}=i;if(g){const G=r.target.value;g.textContent=G,Z()}e.ignoreComposition&&X.value?h=r:s(r)}function oe(){X.value=!0}function Ce(){X.value=!1,e.ignoreComposition&&s(h),h=null}function Se(r){var g;L.value=!0,(g=e.onPatternFocus)===null||g===void 0||g.call(e,r)}function fe(r){var g;L.value=!1,(g=e.onPatternBlur)===null||g===void 0||g.call(e,r)}function le(){var r,g;if(e.filterable)L.value=!1,(r=m.value)===null||r===void 0||r.blur(),(g=f.value)===null||g===void 0||g.blur();else if(e.multiple){const{value:G}=a;G==null||G.blur()}else{const{value:G}=w;G==null||G.blur()}}function Re(){var r,g,G;e.filterable?(L.value=!1,(r=m.value)===null||r===void 0||r.focus()):e.multiple?(g=a.value)===null||g===void 0||g.focus():(G=w.value)===null||G===void 0||G.focus()}function ve(){const{value:r}=f;r&&(ne(),r.focus())}function Me(){const{value:r}=f;r&&r.blur()}function Ie(r){const{value:g}=p;g&&g.setTextContent(`+${r}`)}function ke(){const{value:r}=z;return r}function ze(){return f.value}let be=null;function pe(){be!==null&&window.clearTimeout(be)}function Pe(){e.active||(pe(),be=window.setTimeout(()=>{W.value&&(y.value=!0)},100))}function _e(){pe()}function Be(r){r||(pe(),y.value=!1)}xe(W,r=>{r||(y.value=!1)}),Ne(()=>{mn(()=>{const r=m.value;r&&(e.disabled?r.removeAttribute("tabindex"):r.tabIndex=L.value?-1:0)})}),zt(v,e.onResize);const{inlineThemeDisabled:Fe}=e,me=A(()=>{const{size:r}=e,{common:{cubicBezierEaseInOut:g},self:{fontWeight:G,borderRadius:Ge,color:Xe,placeholderColor:Le,textColor:We,paddingSingle:De,paddingMultiple:Ye,caretColor:Je,colorDisabled:Ve,textColorDisabled:ge,placeholderColorDisabled:t,colorActive:c,boxShadowFocus:x,boxShadowActive:_,boxShadowHover:I,border:M,borderFocus:k,borderHover:Y,borderActive:se,arrowColor:_t,arrowColorDisabled:Bt,loadingColor:$t,colorActiveWarning:At,boxShadowFocusWarning:Et,boxShadowActiveWarning:Nt,boxShadowHoverWarning:Lt,borderWarning:Wt,borderFocusWarning:Dt,borderHoverWarning:Vt,borderActiveWarning:jt,colorActiveError:Ht,boxShadowFocusError:Kt,boxShadowActiveError:Ut,boxShadowHoverError:qt,borderError:Gt,borderFocusError:Xt,borderHoverError:Yt,borderActiveError:Jt,clearColor:Zt,clearColorHover:Qt,clearColorPressed:en,clearSize:tn,arrowSize:nn,[we("height",r)]:on,[we("fontSize",r)]:ln}}=O.value,je=Ae(De),He=Ae(Ye);return{"--n-bezier":g,"--n-border":M,"--n-border-active":se,"--n-border-focus":k,"--n-border-hover":Y,"--n-border-radius":Ge,"--n-box-shadow-active":_,"--n-box-shadow-focus":x,"--n-box-shadow-hover":I,"--n-caret-color":Je,"--n-color":Xe,"--n-color-active":c,"--n-color-disabled":Ve,"--n-font-size":ln,"--n-height":on,"--n-padding-single-top":je.top,"--n-padding-multiple-top":He.top,"--n-padding-single-right":je.right,"--n-padding-multiple-right":He.right,"--n-padding-single-left":je.left,"--n-padding-multiple-left":He.left,"--n-padding-single-bottom":je.bottom,"--n-padding-multiple-bottom":He.bottom,"--n-placeholder-color":Le,"--n-placeholder-color-disabled":t,"--n-text-color":We,"--n-text-color-disabled":ge,"--n-arrow-color":_t,"--n-arrow-color-disabled":Bt,"--n-loading-color":$t,"--n-color-active-warning":At,"--n-box-shadow-focus-warning":Et,"--n-box-shadow-active-warning":Nt,"--n-box-shadow-hover-warning":Lt,"--n-border-warning":Wt,"--n-border-focus-warning":Dt,"--n-border-hover-warning":Vt,"--n-border-active-warning":jt,"--n-color-active-error":Ht,"--n-box-shadow-focus-error":Kt,"--n-box-shadow-active-error":Ut,"--n-box-shadow-hover-error":qt,"--n-border-error":Gt,"--n-border-focus-error":Xt,"--n-border-hover-error":Yt,"--n-border-active-error":Jt,"--n-clear-size":tn,"--n-clear-color":Zt,"--n-clear-color-hover":Qt,"--n-clear-color-pressed":en,"--n-arrow-size":nn,"--n-font-weight":G}}),ee=Fe?ut("internal-selection",A(()=>e.size[0]),me,e):void 0;return{mergedTheme:O,mergedClearable:R,mergedClsPrefix:n,rtlEnabled:l,patternInputFocused:L,filterablePlaceholder:T,label:$,selected:W,showTagsPanel:y,isComposing:X,counterRef:p,counterWrapperRef:z,patternInputMirrorRef:i,patternInputRef:f,selfRef:v,multipleElRef:a,singleElRef:w,patternInputWrapperRef:m,overflowRef:S,inputTagElRef:C,handleMouseDown:j,handleFocusin:b,handleClear:D,handleMouseEnter:q,handleMouseLeave:V,handleDeleteOption:E,handlePatternKeyDown:d,handlePatternInputInput:N,handlePatternInputBlur:fe,handlePatternInputFocus:Se,handleMouseEnterCounter:Pe,handleMouseLeaveCounter:_e,handleFocusout:P,handleCompositionEnd:Ce,handleCompositionStart:oe,onPopoverUpdateShow:Be,focus:Re,focusInput:ve,blur:le,blurInput:Me,updateCounter:Ie,getCounter:ke,getTail:ze,renderLabel:e.renderLabel,cssVars:Fe?void 0:me,themeClass:ee==null?void 0:ee.themeClass,onRender:ee==null?void 0:ee.onRender}},render(){const{status:e,multiple:n,size:o,disabled:l,filterable:i,maxTagCount:f,bordered:v,clsPrefix:a,ellipsisTagPopoverProps:w,onRender:m,renderTag:p,renderLabel:z}=this;m==null||m();const S=f==="responsive",C=typeof f=="number",y=S||C,L=u(gn,null,{default:()=>u(_n,{clsPrefix:a,loading:this.loading,showArrow:this.showArrow,showClear:this.mergedClearable&&this.selected,onClear:this.handleClear},{default:()=>{var O,R;return(R=(O=this.$slots).arrow)===null||R===void 0?void 0:R.call(O)}})});let K;if(n){const{labelField:O}=this,R=s=>u("div",{class:`${a}-base-selection-tag-wrapper`,key:s.value},p?p({option:s,handleClose:()=>{this.handleDeleteOption(s)}}):u(Qe,{size:o,closable:!s.disabled,disabled:l,onClose:()=>{this.handleDeleteOption(s)},internalCloseIsButtonTag:!1,internalCloseFocusable:!1},{default:()=>z?z(s,!0):Te(s[O],s,!0)})),T=()=>(C?this.selectedOptions.slice(0,f):this.selectedOptions).map(R),$=i?u("div",{class:`${a}-base-selection-input-tag`,ref:"inputTagElRef",key:"__input-tag__"},u("input",Object.assign({},this.inputProps,{ref:"patternInputRef",tabindex:-1,disabled:l,value:this.pattern,autofocus:this.autofocus,class:`${a}-base-selection-input-tag__input`,onBlur:this.handlePatternInputBlur,onFocus:this.handlePatternInputFocus,onKeydown:this.handlePatternKeyDown,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),u("span",{ref:"patternInputMirrorRef",class:`${a}-base-selection-input-tag__mirror`},this.pattern)):null,W=S?()=>u("div",{class:`${a}-base-selection-tag-wrapper`,ref:"counterWrapperRef"},u(Qe,{size:o,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,onMouseleave:this.handleMouseLeaveCounter,disabled:l})):void 0;let Z;if(C){const s=this.selectedOptions.length-f;s>0&&(Z=u("div",{class:`${a}-base-selection-tag-wrapper`,key:"__counter__"},u(Qe,{size:o,ref:"counterRef",onMouseenter:this.handleMouseEnterCounter,disabled:l},{default:()=>`+${s}`})))}const U=S?i?u(wt,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,getTail:this.getTail,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:T,counter:W,tail:()=>$}):u(wt,{ref:"overflowRef",updateCounter:this.updateCounter,getCounter:this.getCounter,style:{width:"100%",display:"flex",overflow:"hidden"}},{default:T,counter:W}):C&&Z?T().concat(Z):T(),ne=y?()=>u("div",{class:`${a}-base-selection-popover`},S?T():this.selectedOptions.map(R)):void 0,re=y?Object.assign({show:this.showTagsPanel,trigger:"hover",overlap:!0,placement:"top",width:"trigger",onUpdateShow:this.onPopoverUpdateShow,theme:this.mergedTheme.peers.Popover,themeOverrides:this.mergedTheme.peerOverrides.Popover},w):null,te=(this.selected?!1:this.active?!this.pattern&&!this.isComposing:!0)?u("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`},u("div",{class:`${a}-base-selection-placeholder__inner`},this.placeholder)):null,ae=i?u("div",{ref:"patternInputWrapperRef",class:`${a}-base-selection-tags`},U,S?null:$,L):u("div",{ref:"multipleElRef",class:`${a}-base-selection-tags`,tabindex:l?void 0:0},U,L);K=u(bn,null,y?u(Mn,Object.assign({},re,{scrollable:!0,style:"max-height: calc(var(--v-target-height) * 6.6);"}),{trigger:()=>ae,default:ne}):ae,te)}else if(i){const O=this.pattern||this.isComposing,R=this.active?!O:!this.selected,T=this.active?!1:this.selected;K=u("div",{ref:"patternInputWrapperRef",class:`${a}-base-selection-label`,title:this.patternInputFocused?void 0:yt(this.label)},u("input",Object.assign({},this.inputProps,{ref:"patternInputRef",class:`${a}-base-selection-input`,value:this.active?this.pattern:"",placeholder:"",readonly:l,disabled:l,tabindex:-1,autofocus:this.autofocus,onFocus:this.handlePatternInputFocus,onBlur:this.handlePatternInputBlur,onInput:this.handlePatternInputInput,onCompositionstart:this.handleCompositionStart,onCompositionend:this.handleCompositionEnd})),T?u("div",{class:`${a}-base-selection-label__render-label ${a}-base-selection-overlay`,key:"input"},u("div",{class:`${a}-base-selection-overlay__wrapper`},p?p({option:this.selectedOption,handleClose:()=>{}}):z?z(this.selectedOption,!0):Te(this.label,this.selectedOption,!0))):null,R?u("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`,key:"placeholder"},u("div",{class:`${a}-base-selection-overlay__wrapper`},this.filterablePlaceholder)):null,L)}else K=u("div",{ref:"singleElRef",class:`${a}-base-selection-label`,tabindex:this.disabled?void 0:0},this.label!==void 0?u("div",{class:`${a}-base-selection-input`,title:yt(this.label),key:"input"},u("div",{class:`${a}-base-selection-input__content`},p?p({option:this.selectedOption,handleClose:()=>{}}):z?z(this.selectedOption,!0):Te(this.label,this.selectedOption,!0))):u("div",{class:`${a}-base-selection-placeholder ${a}-base-selection-overlay`,key:"placeholder"},u("div",{class:`${a}-base-selection-placeholder__inner`},this.placeholder)),L);return u("div",{ref:"selfRef",class:[`${a}-base-selection`,this.rtlEnabled&&`${a}-base-selection--rtl`,this.themeClass,e&&`${a}-base-selection--${e}-status`,{[`${a}-base-selection--active`]:this.active,[`${a}-base-selection--selected`]:this.selected||this.active&&this.pattern,[`${a}-base-selection--disabled`]:this.disabled,[`${a}-base-selection--multiple`]:this.multiple,[`${a}-base-selection--focus`]:this.focused}],style:this.cssVars,onClick:this.onClick,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onKeydown:this.onKeydown,onFocusin:this.handleFocusin,onFocusout:this.handleFocusout,onMousedown:this.handleMouseDown},K,v?u("div",{class:`${a}-base-selection__border`}):null,v?u("div",{class:`${a}-base-selection__state-border`}):null)}});function qe(e){return e.type==="group"}function Pt(e){return e.type==="ignored"}function nt(e,n){try{return!!(1+n.toString().toLowerCase().indexOf(e.trim().toLowerCase()))}catch{return!1}}function Yn(e,n){return{getIsGroup:qe,getIgnored:Pt,getKey(l){return qe(l)?l.name||l.key||"key-required":l[e]},getChildren(l){return l[n]}}}function Jn(e,n,o,l){if(!n)return e;function i(f){if(!Array.isArray(f))return[];const v=[];for(const a of f)if(qe(a)){const w=i(a[l]);w.length&&v.push(Object.assign({},a,{[l]:w}))}else{if(Pt(a))continue;n(o,a)&&v.push(a)}return v}return i(e)}function Zn(e,n,o){const l=new Map;return e.forEach(i=>{qe(i)?i[o].forEach(f=>{l.set(f[n],f)}):l.set(i[n],i)}),l}const Qn=ue([B("select",`
 z-index: auto;
 outline: none;
 width: 100%;
 position: relative;
 font-weight: var(--n-font-weight);
 `),B("select-menu",`
 margin: 4px 0;
 box-shadow: var(--n-menu-box-shadow);
 `,[Tt({originalTransition:"background-color .3s var(--n-bezier), box-shadow .3s var(--n-bezier)"})])]),eo=Object.assign(Object.assign({},Oe.props),{to:rt.propTo,bordered:{type:Boolean,default:void 0},clearable:Boolean,clearFilterAfterSelect:{type:Boolean,default:!0},options:{type:Array,default:()=>[]},defaultValue:{type:[String,Number,Array],default:null},keyboard:{type:Boolean,default:!0},value:[String,Number,Array],placeholder:String,menuProps:Object,multiple:Boolean,size:String,menuSize:{type:String},filterable:Boolean,disabled:{type:Boolean,default:void 0},remote:Boolean,loading:Boolean,filter:Function,placement:{type:String,default:"bottom-start"},widthMode:{type:String,default:"trigger"},tag:Boolean,onCreate:Function,fallbackOption:{type:[Function,Boolean],default:void 0},show:{type:Boolean,default:void 0},showArrow:{type:Boolean,default:!0},maxTagCount:[Number,String],ellipsisTagPopoverProps:Object,consistentMenuWidth:{type:Boolean,default:!0},virtualScroll:{type:Boolean,default:!0},labelField:{type:String,default:"label"},valueField:{type:String,default:"value"},childrenField:{type:String,default:"children"},renderLabel:Function,renderOption:Function,renderTag:Function,"onUpdate:value":[Function,Array],inputProps:Object,nodeProps:Function,ignoreComposition:{type:Boolean,default:!0},showOnFocus:Boolean,onUpdateValue:[Function,Array],onBlur:[Function,Array],onClear:[Function,Array],onFocus:[Function,Array],onScroll:[Function,Array],onSearch:[Function,Array],onUpdateShow:[Function,Array],"onUpdate:show":[Function,Array],displayDirective:{type:String,default:"show"},resetMenuOnOptionsChange:{type:Boolean,default:!0},status:String,showCheckmark:{type:Boolean,default:!0},onChange:[Function,Array],items:Array}),uo=ce({name:"Select",props:eo,slots:Object,setup(e){const{mergedClsPrefixRef:n,mergedBorderedRef:o,namespaceRef:l,inlineThemeDisabled:i}=dt(e),f=Oe("Select","-select",Qn,Fn,e,n),v=F(e.defaultValue),a=J(e,"value"),w=gt(a,v),m=F(!1),p=F(""),z=Pn(e,["items","options"]),S=F([]),C=F([]),y=A(()=>C.value.concat(S.value).concat(z.value)),L=A(()=>{const{filter:t}=e;if(t)return t;const{labelField:c,valueField:x}=e;return(_,I)=>{if(!I)return!1;const M=I[c];if(typeof M=="string")return nt(_,M);const k=I[x];return typeof k=="string"?nt(_,k):typeof k=="number"?nt(_,String(k)):!1}}),K=A(()=>{if(e.remote)return z.value;{const{value:t}=y,{value:c}=p;return!c.length||!e.filterable?t:Jn(t,L.value,c,e.childrenField)}}),O=A(()=>{const{valueField:t,childrenField:c}=e,x=Yn(t,c);return $n(K.value,x)}),R=A(()=>Zn(y.value,e.valueField,e.childrenField)),T=F(!1),$=gt(J(e,"show"),T),W=F(null),Z=F(null),U=F(null),{localeRef:ne}=En("Select"),re=A(()=>{var t;return(t=e.placeholder)!==null&&t!==void 0?t:ne.value.placeholder}),Q=[],te=F(new Map),ae=A(()=>{const{fallbackOption:t}=e;if(t===void 0){const{labelField:c,valueField:x}=e;return _=>({[c]:String(_),[x]:_})}return t===!1?!1:c=>Object.assign(t(c),{value:c})});function s(t){const c=e.remote,{value:x}=te,{value:_}=R,{value:I}=ae,M=[];return t.forEach(k=>{if(_.has(k))M.push(_.get(k));else if(c&&x.has(k))M.push(x.get(k));else if(I){const Y=I(k);Y&&M.push(Y)}}),M}const b=A(()=>{if(e.multiple){const{value:t}=w;return Array.isArray(t)?s(t):[]}return null}),P=A(()=>{const{value:t}=w;return!e.multiple&&!Array.isArray(t)?t===null?null:s([t])[0]||null:null}),D=xn(e),{mergedSizeRef:q,mergedDisabledRef:V,mergedStatusRef:j}=D;function E(t,c){const{onChange:x,"onUpdate:value":_,onUpdateValue:I}=e,{nTriggerFormChange:M,nTriggerFormInput:k}=D;x&&de(x,t,c),I&&de(I,t,c),_&&de(_,t,c),v.value=t,M(),k()}function X(t){const{onBlur:c}=e,{nTriggerFormBlur:x}=D;c&&de(c,t),x()}function d(){const{onClear:t}=e;t&&de(t)}function h(t){const{onFocus:c,showOnFocus:x}=e,{nTriggerFormFocus:_}=D;c&&de(c,t),_(),x&&fe()}function N(t){const{onSearch:c}=e;c&&de(c,t)}function oe(t){const{onScroll:c}=e;c&&de(c,t)}function Ce(){var t;const{remote:c,multiple:x}=e;if(c){const{value:_}=te;if(x){const{valueField:I}=e;(t=b.value)===null||t===void 0||t.forEach(M=>{_.set(M[I],M)})}else{const I=P.value;I&&_.set(I[e.valueField],I)}}}function Se(t){const{onUpdateShow:c,"onUpdate:show":x}=e;c&&de(c,t),x&&de(x,t),T.value=t}function fe(){V.value||(Se(!0),T.value=!0,e.filterable&&De())}function le(){Se(!1)}function Re(){p.value="",C.value=Q}const ve=F(!1);function Me(){e.filterable&&(ve.value=!0)}function Ie(){e.filterable&&(ve.value=!1,$.value||Re())}function ke(){V.value||($.value?e.filterable?De():le():fe())}function ze(t){var c,x;!((x=(c=U.value)===null||c===void 0?void 0:c.selfRef)===null||x===void 0)&&x.contains(t.relatedTarget)||(m.value=!1,X(t),le())}function be(t){h(t),m.value=!0}function pe(){m.value=!0}function Pe(t){var c;!((c=W.value)===null||c===void 0)&&c.$el.contains(t.relatedTarget)||(m.value=!1,X(t),le())}function _e(){var t;(t=W.value)===null||t===void 0||t.focus(),le()}function Be(t){var c;$.value&&(!((c=W.value)===null||c===void 0)&&c.$el.contains(Sn(t))||le())}function Fe(t){if(!Array.isArray(t))return[];if(ae.value)return Array.from(t);{const{remote:c}=e,{value:x}=R;if(c){const{value:_}=te;return t.filter(I=>x.has(I)||_.has(I))}else return t.filter(_=>x.has(_))}}function me(t){ee(t.rawNode)}function ee(t){if(V.value)return;const{tag:c,remote:x,clearFilterAfterSelect:_,valueField:I}=e;if(c&&!x){const{value:M}=C,k=M[0]||null;if(k){const Y=S.value;Y.length?Y.push(k):S.value=[k],C.value=Q}}if(x&&te.value.set(t[I],t),e.multiple){const M=Fe(w.value),k=M.findIndex(Y=>Y===t[I]);if(~k){if(M.splice(k,1),c&&!x){const Y=r(t[I]);~Y&&(S.value.splice(Y,1),_&&(p.value=""))}}else M.push(t[I]),_&&(p.value="");E(M,s(M))}else{if(c&&!x){const M=r(t[I]);~M?S.value=[S.value[M]]:S.value=Q}We(),le(),E(t[I],t)}}function r(t){return S.value.findIndex(x=>x[e.valueField]===t)}function g(t){$.value||fe();const{value:c}=t.target;p.value=c;const{tag:x,remote:_}=e;if(N(c),x&&!_){if(!c){C.value=Q;return}const{onCreate:I}=e,M=I?I(c):{[e.labelField]:c,[e.valueField]:c},{valueField:k,labelField:Y}=e;z.value.some(se=>se[k]===M[k]||se[Y]===M[Y])||S.value.some(se=>se[k]===M[k]||se[Y]===M[Y])?C.value=Q:C.value=[M]}}function G(t){t.stopPropagation();const{multiple:c}=e;!c&&e.filterable&&le(),d(),c?E([],[]):E(null,null)}function Ge(t){!Ee(t,"action")&&!Ee(t,"empty")&&!Ee(t,"header")&&t.preventDefault()}function Xe(t){oe(t)}function Le(t){var c,x,_,I,M;if(!e.keyboard){t.preventDefault();return}switch(t.key){case" ":if(e.filterable)break;t.preventDefault();case"Enter":if(!(!((c=W.value)===null||c===void 0)&&c.isComposing)){if($.value){const k=(x=U.value)===null||x===void 0?void 0:x.getPendingTmNode();k?me(k):e.filterable||(le(),We())}else if(fe(),e.tag&&ve.value){const k=C.value[0];if(k){const Y=k[e.valueField],{value:se}=w;e.multiple&&Array.isArray(se)&&se.includes(Y)||ee(k)}}}t.preventDefault();break;case"ArrowUp":if(t.preventDefault(),e.loading)return;$.value&&((_=U.value)===null||_===void 0||_.prev());break;case"ArrowDown":if(t.preventDefault(),e.loading)return;$.value?(I=U.value)===null||I===void 0||I.next():fe();break;case"Escape":$.value&&(Rn(t),le()),(M=W.value)===null||M===void 0||M.focus();break}}function We(){var t;(t=W.value)===null||t===void 0||t.focus()}function De(){var t;(t=W.value)===null||t===void 0||t.focusInput()}function Ye(){var t;$.value&&((t=Z.value)===null||t===void 0||t.syncPosition())}Ce(),xe(J(e,"options"),Ce);const Je={focus:()=>{var t;(t=W.value)===null||t===void 0||t.focus()},focusInput:()=>{var t;(t=W.value)===null||t===void 0||t.focusInput()},blur:()=>{var t;(t=W.value)===null||t===void 0||t.blur()},blurInput:()=>{var t;(t=W.value)===null||t===void 0||t.blurInput()}},Ve=A(()=>{const{self:{menuBoxShadow:t}}=f.value;return{"--n-menu-box-shadow":t}}),ge=i?ut("select",void 0,Ve,e):void 0;return Object.assign(Object.assign({},Je),{mergedStatus:j,mergedClsPrefix:n,mergedBordered:o,namespace:l,treeMate:O,isMounted:Cn(),triggerRef:W,menuRef:U,pattern:p,uncontrolledShow:T,mergedShow:$,adjustedTo:rt(e),uncontrolledValue:v,mergedValue:w,followerRef:Z,localizedPlaceholder:re,selectedOption:P,selectedOptions:b,mergedSize:q,mergedDisabled:V,focused:m,activeWithoutMenuOpen:ve,inlineThemeDisabled:i,onTriggerInputFocus:Me,onTriggerInputBlur:Ie,handleTriggerOrMenuResize:Ye,handleMenuFocus:pe,handleMenuBlur:Pe,handleMenuTabOut:_e,handleTriggerClick:ke,handleToggle:me,handleDeleteOption:ee,handlePatternInput:g,handleClear:G,handleTriggerBlur:ze,handleTriggerFocus:be,handleKeydown:Le,handleMenuAfterLeave:Re,handleMenuClickOutside:Be,handleMenuScroll:Xe,handleMenuKeydown:Le,handleMenuMousedown:Ge,mergedTheme:f,cssVars:i?void 0:Ve,themeClass:ge==null?void 0:ge.themeClass,onRender:ge==null?void 0:ge.onRender})},render(){return u("div",{class:`${this.mergedClsPrefix}-select`},u(In,null,{default:()=>[u(kn,null,{default:()=>u(Xn,{ref:"triggerRef",inlineThemeDisabled:this.inlineThemeDisabled,status:this.mergedStatus,inputProps:this.inputProps,clsPrefix:this.mergedClsPrefix,showArrow:this.showArrow,maxTagCount:this.maxTagCount,ellipsisTagPopoverProps:this.ellipsisTagPopoverProps,bordered:this.mergedBordered,active:this.activeWithoutMenuOpen||this.mergedShow,pattern:this.pattern,placeholder:this.localizedPlaceholder,selectedOption:this.selectedOption,selectedOptions:this.selectedOptions,multiple:this.multiple,renderTag:this.renderTag,renderLabel:this.renderLabel,filterable:this.filterable,clearable:this.clearable,disabled:this.mergedDisabled,size:this.mergedSize,theme:this.mergedTheme.peers.InternalSelection,labelField:this.labelField,valueField:this.valueField,themeOverrides:this.mergedTheme.peerOverrides.InternalSelection,loading:this.loading,focused:this.focused,onClick:this.handleTriggerClick,onDeleteOption:this.handleDeleteOption,onPatternInput:this.handlePatternInput,onClear:this.handleClear,onBlur:this.handleTriggerBlur,onFocus:this.handleTriggerFocus,onKeydown:this.handleKeydown,onPatternBlur:this.onTriggerInputBlur,onPatternFocus:this.onTriggerInputFocus,onResize:this.handleTriggerOrMenuResize,ignoreComposition:this.ignoreComposition},{arrow:()=>{var e,n;return[(n=(e=this.$slots).arrow)===null||n===void 0?void 0:n.call(e)]}})}),u(zn,{ref:"followerRef",show:this.mergedShow,to:this.adjustedTo,teleportDisabled:this.adjustedTo===rt.tdkey,containerClass:this.namespace,width:this.consistentMenuWidth?"target":void 0,minWidth:"target",placement:this.placement},{default:()=>u(Ft,{name:"fade-in-scale-up-transition",appear:this.isMounted,onAfterLeave:this.handleMenuAfterLeave},{default:()=>{var e,n,o;return this.mergedShow||this.displayDirective==="show"?((e=this.onRender)===null||e===void 0||e.call(this),wn(u(qn,Object.assign({},this.menuProps,{ref:"menuRef",onResize:this.handleTriggerOrMenuResize,inlineThemeDisabled:this.inlineThemeDisabled,virtualScroll:this.consistentMenuWidth&&this.virtualScroll,class:[`${this.mergedClsPrefix}-select-menu`,this.themeClass,(n=this.menuProps)===null||n===void 0?void 0:n.class],clsPrefix:this.mergedClsPrefix,focusable:!0,labelField:this.labelField,valueField:this.valueField,autoPending:!0,nodeProps:this.nodeProps,theme:this.mergedTheme.peers.InternalSelectMenu,themeOverrides:this.mergedTheme.peerOverrides.InternalSelectMenu,treeMate:this.treeMate,multiple:this.multiple,size:this.menuSize,renderOption:this.renderOption,renderLabel:this.renderLabel,value:this.mergedValue,style:[(o=this.menuProps)===null||o===void 0?void 0:o.style,this.cssVars],onToggle:this.handleToggle,onScroll:this.handleMenuScroll,onFocus:this.handleMenuFocus,onBlur:this.handleMenuBlur,onKeydown:this.handleMenuKeydown,onTabOut:this.handleMenuTabOut,onMousedown:this.handleMenuMousedown,show:this.mergedShow,showCheckmark:this.showCheckmark,resetMenuOnOptionsChange:this.resetMenuOnOptionsChange}),{empty:()=>{var l,i;return[(i=(l=this.$slots).empty)===null||i===void 0?void 0:i.call(l)]},header:()=>{var l,i;return[(i=(l=this.$slots).header)===null||i===void 0?void 0:i.call(l)]},action:()=>{var l,i;return[(i=(l=this.$slots).action)===null||i===void 0?void 0:i.call(l)]}}),this.displayDirective==="show"?[[yn,this.mergedShow],[vt,this.handleMenuClickOutside,void 0,{capture:!0}]]:[[vt,this.handleMenuClickOutside,void 0,{capture:!0}]])):null}})})]}))}});export{Hn as F,qn as N,uo as _,Yn as c,tt as m};
