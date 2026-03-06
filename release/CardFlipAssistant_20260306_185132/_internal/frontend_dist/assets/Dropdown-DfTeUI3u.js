import{B as xe,V as Se,a as Ne,r as Pe,_ as Re,p as ae}from"./Popover-DgS4fGBY.js";import{r as F,s as se,P as re,k as j,D as l,bD as V,S as T,a1 as ue,a0 as ke,n as w,b2 as G,a9 as ce,L as H,F as Ke,b3 as Ie,bP as _e,aa as Ce,a8 as Oe,E as x,aW as De,G as E,au as ie,I as k,H as D,at as $e,M as K,J as ze,K as pe,ax as A,N as Ae,ai as oe,bQ as Fe}from"./index-Cy6T1kuG.js";import{N as Te}from"./Icon-WEQoZj2_.js";import{C as je}from"./ChevronRight-CKjhZ34L.js";import{h as de}from"./happens-in-CM8LO42l.js";import{u as Be}from"./use-merged-state-Br1y0BqO.js";import{c as Me}from"./create-Co-OdYMQ.js";import{u as Le}from"./use-keyboard-BOITeFpJ.js";function Ee(e,n,a){const t=F(e.value);let r=null;return se(e,o=>{r!==null&&window.clearTimeout(r),o===!0?a&&!a.value?t.value=!0:r=window.setTimeout(()=>{t.value=!0},n):t.value=!1}),t}function He(e){return n=>{n?e.value=n.$el:e.value=null}}const te=re("n-dropdown-menu"),J=re("n-dropdown"),le=re("n-dropdown-option"),fe=j({name:"DropdownDivider",props:{clsPrefix:{type:String,required:!0}},render(){return l("div",{class:`${this.clsPrefix}-dropdown-divider`})}}),Ue=j({name:"DropdownGroupHeader",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0}},setup(){const{showIconRef:e,hasSubmenuRef:n}=T(te),{renderLabelRef:a,labelFieldRef:t,nodePropsRef:r,renderOptionRef:o}=T(J);return{labelField:t,showIcon:e,hasSubmenu:n,renderLabel:a,nodeProps:r,renderOption:o}},render(){var e;const{clsPrefix:n,hasSubmenu:a,showIcon:t,nodeProps:r,renderLabel:o,renderOption:p}=this,{rawNode:f}=this.tmNode,c=l("div",Object.assign({class:`${n}-dropdown-option`},r==null?void 0:r(f)),l("div",{class:`${n}-dropdown-option-body ${n}-dropdown-option-body--group`},l("div",{"data-dropdown-option":!0,class:[`${n}-dropdown-option-body__prefix`,t&&`${n}-dropdown-option-body__prefix--show-icon`]},V(f.icon)),l("div",{class:`${n}-dropdown-option-body__label`,"data-dropdown-option":!0},o?o(f):V((e=f.title)!==null&&e!==void 0?e:f[this.labelField])),l("div",{class:[`${n}-dropdown-option-body__suffix`,a&&`${n}-dropdown-option-body__suffix--has-submenu`],"data-dropdown-option":!0})));return p?p({node:c,option:f}):c}});function ne(e,n){return e.type==="submenu"||e.type===void 0&&e[n]!==void 0}function We(e){return e.type==="group"}function ve(e){return e.type==="divider"}function qe(e){return e.type==="render"}const he=j({name:"DropdownOption",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0},parentKey:{type:[String,Number],default:null},placement:{type:String,default:"right-start"},props:Object,scrollable:Boolean},setup(e){const n=T(J),{hoverKeyRef:a,keyboardKeyRef:t,lastToggledSubmenuKeyRef:r,pendingKeyPathRef:o,activeKeyPathRef:p,animatedRef:f,mergedShowRef:c,renderLabelRef:S,renderIconRef:g,labelFieldRef:N,childrenFieldRef:I,renderOptionRef:P,nodePropsRef:_,menuPropsRef:B}=n,m=T(le,null),C=T(te),U=T(ce),Q=w(()=>e.tmNode.rawNode),W=w(()=>{const{value:d}=I;return ne(e.tmNode.rawNode,d)}),X=w(()=>{const{disabled:d}=e.tmNode;return d}),Y=w(()=>{if(!W.value)return!1;const{key:d,disabled:b}=e.tmNode;if(b)return!1;const{value:R}=a,{value:$}=t,{value:ee}=r,{value:z}=o;return R!==null?z.includes(d):$!==null?z.includes(d)&&z[z.length-1]!==d:ee!==null?z.includes(d):!1}),Z=w(()=>t.value===null&&!f.value),q=Ee(Y,300,Z),M=w(()=>!!(m!=null&&m.enteringSubmenuRef.value)),L=F(!1);H(le,{enteringSubmenuRef:L});function O(){L.value=!0}function i(){L.value=!1}function h(){const{parentKey:d,tmNode:b}=e;b.disabled||c.value&&(r.value=d,t.value=null,a.value=b.key)}function u(){const{tmNode:d}=e;d.disabled||c.value&&a.value!==d.key&&h()}function s(d){if(e.tmNode.disabled||!c.value)return;const{relatedTarget:b}=d;b&&!de({target:b},"dropdownOption")&&!de({target:b},"scrollbarRail")&&(a.value=null)}function y(){const{value:d}=W,{tmNode:b}=e;c.value&&!d&&!b.disabled&&(n.doSelect(b.key,b.rawNode),n.doUpdateShow(!1))}return{labelField:N,renderLabel:S,renderIcon:g,siblingHasIcon:C.showIconRef,siblingHasSubmenu:C.hasSubmenuRef,menuProps:B,popoverBody:U,animated:f,mergedShowSubmenu:w(()=>q.value&&!M.value),rawNode:Q,hasSubmenu:W,pending:G(()=>{const{value:d}=o,{key:b}=e.tmNode;return d.includes(b)}),childActive:G(()=>{const{value:d}=p,{key:b}=e.tmNode,R=d.findIndex($=>b===$);return R===-1?!1:R<d.length-1}),active:G(()=>{const{value:d}=p,{key:b}=e.tmNode,R=d.findIndex($=>b===$);return R===-1?!1:R===d.length-1}),mergedDisabled:X,renderOption:P,nodeProps:_,handleClick:y,handleMouseMove:u,handleMouseEnter:h,handleMouseLeave:s,handleSubmenuBeforeEnter:O,handleSubmenuAfterEnter:i}},render(){var e,n;const{animated:a,rawNode:t,mergedShowSubmenu:r,clsPrefix:o,siblingHasIcon:p,siblingHasSubmenu:f,renderLabel:c,renderIcon:S,renderOption:g,nodeProps:N,props:I,scrollable:P}=this;let _=null;if(r){const U=(e=this.menuProps)===null||e===void 0?void 0:e.call(this,t,t.children);_=l(be,Object.assign({},U,{clsPrefix:o,scrollable:this.scrollable,tmNodes:this.tmNode.children,parentKey:this.tmNode.key}))}const B={class:[`${o}-dropdown-option-body`,this.pending&&`${o}-dropdown-option-body--pending`,this.active&&`${o}-dropdown-option-body--active`,this.childActive&&`${o}-dropdown-option-body--child-active`,this.mergedDisabled&&`${o}-dropdown-option-body--disabled`],onMousemove:this.handleMouseMove,onMouseenter:this.handleMouseEnter,onMouseleave:this.handleMouseLeave,onClick:this.handleClick},m=N==null?void 0:N(t),C=l("div",Object.assign({class:[`${o}-dropdown-option`,m==null?void 0:m.class],"data-dropdown-option":!0},m),l("div",ue(B,I),[l("div",{class:[`${o}-dropdown-option-body__prefix`,p&&`${o}-dropdown-option-body__prefix--show-icon`]},[S?S(t):V(t.icon)]),l("div",{"data-dropdown-option":!0,class:`${o}-dropdown-option-body__label`},c?c(t):V((n=t[this.labelField])!==null&&n!==void 0?n:t.title)),l("div",{"data-dropdown-option":!0,class:[`${o}-dropdown-option-body__suffix`,f&&`${o}-dropdown-option-body__suffix--has-submenu`]},this.hasSubmenu?l(Te,null,{default:()=>l(je,null)}):null)]),this.hasSubmenu?l(xe,null,{default:()=>[l(Se,null,{default:()=>l("div",{class:`${o}-dropdown-offset-container`},l(Ne,{show:this.mergedShowSubmenu,placement:this.placement,to:P&&this.popoverBody||void 0,teleportDisabled:!P},{default:()=>l("div",{class:`${o}-dropdown-menu-wrapper`},a?l(ke,{onBeforeEnter:this.handleSubmenuBeforeEnter,onAfterEnter:this.handleSubmenuAfterEnter,name:"fade-in-scale-up-transition",appear:!0},{default:()=>_}):_)}))})]}):null);return g?g({node:C,option:t}):C}}),Ge=j({name:"NDropdownGroup",props:{clsPrefix:{type:String,required:!0},tmNode:{type:Object,required:!0},parentKey:{type:[String,Number],default:null}},render(){const{tmNode:e,parentKey:n,clsPrefix:a}=this,{children:t}=e;return l(Ke,null,l(Ue,{clsPrefix:a,tmNode:e,key:e.key}),t==null?void 0:t.map(r=>{const{rawNode:o}=r;return o.show===!1?null:ve(o)?l(fe,{clsPrefix:a,key:r.key}):r.isGroup?(Ie("dropdown","`group` node is not allowed to be put in `group` node."),null):l(he,{clsPrefix:a,tmNode:r,parentKey:n,key:r.key})}))}}),Ve=j({name:"DropdownRenderOption",props:{tmNode:{type:Object,required:!0}},render(){const{rawNode:{render:e,props:n}}=this.tmNode;return l("div",n,[e==null?void 0:e()])}}),be=j({name:"DropdownMenu",props:{scrollable:Boolean,showArrow:Boolean,arrowStyle:[String,Object],clsPrefix:{type:String,required:!0},tmNodes:{type:Array,default:()=>[]},parentKey:{type:[String,Number],default:null}},setup(e){const{renderIconRef:n,childrenFieldRef:a}=T(J);H(te,{showIconRef:w(()=>{const r=n.value;return e.tmNodes.some(o=>{var p;if(o.isGroup)return(p=o.children)===null||p===void 0?void 0:p.some(({rawNode:c})=>r?r(c):c.icon);const{rawNode:f}=o;return r?r(f):f.icon})}),hasSubmenuRef:w(()=>{const{value:r}=a;return e.tmNodes.some(o=>{var p;if(o.isGroup)return(p=o.children)===null||p===void 0?void 0:p.some(({rawNode:c})=>ne(c,r));const{rawNode:f}=o;return ne(f,r)})})});const t=F(null);return H(Ce,null),H(Oe,null),H(ce,t),{bodyRef:t}},render(){const{parentKey:e,clsPrefix:n,scrollable:a}=this,t=this.tmNodes.map(r=>{const{rawNode:o}=r;return o.show===!1?null:qe(o)?l(Ve,{tmNode:r,key:r.key}):ve(o)?l(fe,{clsPrefix:n,key:r.key}):We(o)?l(Ge,{clsPrefix:n,tmNode:r,parentKey:e,key:r.key}):l(he,{clsPrefix:n,tmNode:r,parentKey:e,key:r.key,props:o.props,scrollable:a})});return l("div",{class:[`${n}-dropdown-menu`,a&&`${n}-dropdown-menu--scrollable`],ref:"bodyRef"},a?l(_e,{contentClass:`${n}-dropdown-menu__content`},{default:()=>t}):t,this.showArrow?Pe({clsPrefix:n,arrowStyle:this.arrowStyle,arrowClass:void 0,arrowWrapperClass:void 0,arrowWrapperStyle:void 0}):null)}}),Je=x("dropdown-menu",`
 transform-origin: var(--v-transform-origin);
 background-color: var(--n-color);
 border-radius: var(--n-border-radius);
 box-shadow: var(--n-box-shadow);
 position: relative;
 transition:
 background-color .3s var(--n-bezier),
 box-shadow .3s var(--n-bezier);
`,[De(),x("dropdown-option",`
 position: relative;
 `,[E("a",`
 text-decoration: none;
 color: inherit;
 outline: none;
 `,[E("&::before",`
 content: "";
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `)]),x("dropdown-option-body",`
 display: flex;
 cursor: pointer;
 position: relative;
 height: var(--n-option-height);
 line-height: var(--n-option-height);
 font-size: var(--n-font-size);
 color: var(--n-option-text-color);
 transition: color .3s var(--n-bezier);
 `,[E("&::before",`
 content: "";
 position: absolute;
 top: 0;
 bottom: 0;
 left: 4px;
 right: 4px;
 transition: background-color .3s var(--n-bezier);
 border-radius: var(--n-border-radius);
 `),ie("disabled",[k("pending",`
 color: var(--n-option-text-color-hover);
 `,[D("prefix, suffix",`
 color: var(--n-option-text-color-hover);
 `),E("&::before","background-color: var(--n-option-color-hover);")]),k("active",`
 color: var(--n-option-text-color-active);
 `,[D("prefix, suffix",`
 color: var(--n-option-text-color-active);
 `),E("&::before","background-color: var(--n-option-color-active);")]),k("child-active",`
 color: var(--n-option-text-color-child-active);
 `,[D("prefix, suffix",`
 color: var(--n-option-text-color-child-active);
 `)])]),k("disabled",`
 cursor: not-allowed;
 opacity: var(--n-option-opacity-disabled);
 `),k("group",`
 font-size: calc(var(--n-font-size) - 1px);
 color: var(--n-group-header-text-color);
 `,[D("prefix",`
 width: calc(var(--n-option-prefix-width) / 2);
 `,[k("show-icon",`
 width: calc(var(--n-option-icon-prefix-width) / 2);
 `)])]),D("prefix",`
 width: var(--n-option-prefix-width);
 display: flex;
 justify-content: center;
 align-items: center;
 color: var(--n-prefix-color);
 transition: color .3s var(--n-bezier);
 z-index: 1;
 `,[k("show-icon",`
 width: var(--n-option-icon-prefix-width);
 `),x("icon",`
 font-size: var(--n-option-icon-size);
 `)]),D("label",`
 white-space: nowrap;
 flex: 1;
 z-index: 1;
 `),D("suffix",`
 box-sizing: border-box;
 flex-grow: 0;
 flex-shrink: 0;
 display: flex;
 justify-content: flex-end;
 align-items: center;
 min-width: var(--n-option-suffix-width);
 padding: 0 8px;
 transition: color .3s var(--n-bezier);
 color: var(--n-suffix-color);
 z-index: 1;
 `,[k("has-submenu",`
 width: var(--n-option-icon-suffix-width);
 `),x("icon",`
 font-size: var(--n-option-icon-size);
 `)]),x("dropdown-menu","pointer-events: all;")]),x("dropdown-offset-container",`
 pointer-events: none;
 position: absolute;
 left: 0;
 right: 0;
 top: -4px;
 bottom: -4px;
 `)]),x("dropdown-divider",`
 transition: background-color .3s var(--n-bezier);
 background-color: var(--n-divider-color);
 height: 1px;
 margin: 4px 0;
 `),x("dropdown-menu-wrapper",`
 transform-origin: var(--v-transform-origin);
 width: fit-content;
 `),E(">",[x("scrollbar",`
 height: inherit;
 max-height: inherit;
 `)]),ie("scrollable",`
 padding: var(--n-padding);
 `),k("scrollable",[D("content",`
 padding: var(--n-padding);
 `)])]),Qe={animated:{type:Boolean,default:!0},keyboard:{type:Boolean,default:!0},size:{type:String,default:"medium"},inverted:Boolean,placement:{type:String,default:"bottom"},onSelect:[Function,Array],options:{type:Array,default:()=>[]},menuProps:Function,showArrow:Boolean,renderLabel:Function,renderIcon:Function,renderOption:Function,nodeProps:Function,labelField:{type:String,default:"label"},keyField:{type:String,default:"key"},childrenField:{type:String,default:"children"},value:[String,Number]},Xe=Object.keys(ae),Ye=Object.assign(Object.assign(Object.assign({},ae),Qe),pe.props),ao=j({name:"Dropdown",inheritAttrs:!1,props:Ye,setup(e){const n=F(!1),a=Be(K(e,"show"),n),t=w(()=>{const{keyField:i,childrenField:h}=e;return Me(e.options,{getKey(u){return u[i]},getDisabled(u){return u.disabled===!0},getIgnored(u){return u.type==="divider"||u.type==="render"},getChildren(u){return u[h]}})}),r=w(()=>t.value.treeNodes),o=F(null),p=F(null),f=F(null),c=w(()=>{var i,h,u;return(u=(h=(i=o.value)!==null&&i!==void 0?i:p.value)!==null&&h!==void 0?h:f.value)!==null&&u!==void 0?u:null}),S=w(()=>t.value.getPath(c.value).keyPath),g=w(()=>t.value.getPath(e.value).keyPath),N=G(()=>e.keyboard&&a.value);Le({keydown:{ArrowUp:{prevent:!0,handler:X},ArrowRight:{prevent:!0,handler:W},ArrowDown:{prevent:!0,handler:Y},ArrowLeft:{prevent:!0,handler:Q},Enter:{prevent:!0,handler:Z},Escape:U}},N);const{mergedClsPrefixRef:I,inlineThemeDisabled:P}=ze(e),_=pe("Dropdown","-dropdown",Je,Fe,e,I);H(J,{labelFieldRef:K(e,"labelField"),childrenFieldRef:K(e,"childrenField"),renderLabelRef:K(e,"renderLabel"),renderIconRef:K(e,"renderIcon"),hoverKeyRef:o,keyboardKeyRef:p,lastToggledSubmenuKeyRef:f,pendingKeyPathRef:S,activeKeyPathRef:g,animatedRef:K(e,"animated"),mergedShowRef:a,nodePropsRef:K(e,"nodeProps"),renderOptionRef:K(e,"renderOption"),menuPropsRef:K(e,"menuProps"),doSelect:B,doUpdateShow:m}),se(a,i=>{!e.animated&&!i&&C()});function B(i,h){const{onSelect:u}=e;u&&oe(u,i,h)}function m(i){const{"onUpdate:show":h,onUpdateShow:u}=e;h&&oe(h,i),u&&oe(u,i),n.value=i}function C(){o.value=null,p.value=null,f.value=null}function U(){m(!1)}function Q(){M("left")}function W(){M("right")}function X(){M("up")}function Y(){M("down")}function Z(){const i=q();i!=null&&i.isLeaf&&a.value&&(B(i.key,i.rawNode),m(!1))}function q(){var i;const{value:h}=t,{value:u}=c;return!h||u===null?null:(i=h.getNode(u))!==null&&i!==void 0?i:null}function M(i){const{value:h}=c,{value:{getFirstAvailableNode:u}}=t;let s=null;if(h===null){const y=u();y!==null&&(s=y.key)}else{const y=q();if(y){let d;switch(i){case"down":d=y.getNext();break;case"up":d=y.getPrev();break;case"right":d=y.getChild();break;case"left":d=y.getParent();break}d&&(s=d.key)}}s!==null&&(o.value=null,p.value=s)}const L=w(()=>{const{size:i,inverted:h}=e,{common:{cubicBezierEaseInOut:u},self:s}=_.value,{padding:y,dividerColor:d,borderRadius:b,optionOpacityDisabled:R,[A("optionIconSuffixWidth",i)]:$,[A("optionSuffixWidth",i)]:ee,[A("optionIconPrefixWidth",i)]:z,[A("optionPrefixWidth",i)]:we,[A("fontSize",i)]:me,[A("optionHeight",i)]:ye,[A("optionIconSize",i)]:ge}=s,v={"--n-bezier":u,"--n-font-size":me,"--n-padding":y,"--n-border-radius":b,"--n-option-height":ye,"--n-option-prefix-width":we,"--n-option-icon-prefix-width":z,"--n-option-suffix-width":ee,"--n-option-icon-suffix-width":$,"--n-option-icon-size":ge,"--n-divider-color":d,"--n-option-opacity-disabled":R};return h?(v["--n-color"]=s.colorInverted,v["--n-option-color-hover"]=s.optionColorHoverInverted,v["--n-option-color-active"]=s.optionColorActiveInverted,v["--n-option-text-color"]=s.optionTextColorInverted,v["--n-option-text-color-hover"]=s.optionTextColorHoverInverted,v["--n-option-text-color-active"]=s.optionTextColorActiveInverted,v["--n-option-text-color-child-active"]=s.optionTextColorChildActiveInverted,v["--n-prefix-color"]=s.prefixColorInverted,v["--n-suffix-color"]=s.suffixColorInverted,v["--n-group-header-text-color"]=s.groupHeaderTextColorInverted):(v["--n-color"]=s.color,v["--n-option-color-hover"]=s.optionColorHover,v["--n-option-color-active"]=s.optionColorActive,v["--n-option-text-color"]=s.optionTextColor,v["--n-option-text-color-hover"]=s.optionTextColorHover,v["--n-option-text-color-active"]=s.optionTextColorActive,v["--n-option-text-color-child-active"]=s.optionTextColorChildActive,v["--n-prefix-color"]=s.prefixColor,v["--n-suffix-color"]=s.suffixColor,v["--n-group-header-text-color"]=s.groupHeaderTextColor),v}),O=P?Ae("dropdown",w(()=>`${e.size[0]}${e.inverted?"i":""}`),L,e):void 0;return{mergedClsPrefix:I,mergedTheme:_,tmNodes:r,mergedShow:a,handleAfterLeave:()=>{e.animated&&C()},doUpdateShow:m,cssVars:P?void 0:L,themeClass:O==null?void 0:O.themeClass,onRender:O==null?void 0:O.onRender}},render(){const e=(t,r,o,p,f)=>{var c;const{mergedClsPrefix:S,menuProps:g}=this;(c=this.onRender)===null||c===void 0||c.call(this);const N=(g==null?void 0:g(void 0,this.tmNodes.map(P=>P.rawNode)))||{},I={ref:He(r),class:[t,`${S}-dropdown`,this.themeClass],clsPrefix:S,tmNodes:this.tmNodes,style:[...o,this.cssVars],showArrow:this.showArrow,arrowStyle:this.arrowStyle,scrollable:this.scrollable,onMouseenter:p,onMouseleave:f};return l(be,ue(this.$attrs,I,N))},{mergedTheme:n}=this,a={show:this.mergedShow,theme:n.peers.Popover,themeOverrides:n.peerOverrides.Popover,internalOnAfterLeave:this.handleAfterLeave,internalRenderBody:e,onUpdateShow:this.doUpdateShow,"onUpdate:show":void 0};return l(Re,Object.assign({},$e(this.$props,Xe),a),{trigger:()=>{var t,r;return(r=(t=this.$slots).default)===null||r===void 0?void 0:r.call(t)}})}});export{ao as _,He as c};
