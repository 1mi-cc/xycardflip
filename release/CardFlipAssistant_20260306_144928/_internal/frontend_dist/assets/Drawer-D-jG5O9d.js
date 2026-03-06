import{k as X,W as P,D as u,$ as fe,a0 as Y,a1 as me,U as be,X as L,r as B,n as p,J as K,a2 as ge,S as ve,a3 as pe,s as we,a4 as ye,a5 as ze,a6 as $e,a7 as V,L as H,a8 as Se,a9 as xe,aa as Be,G as i,ab as M,E as c,I as g,H as $,ac as Ce,ad as ke,ae as Ee,af as Re,K as q,M as N,ag as Fe,N as He,ah as Me,ai as S,aj as Te}from"./index-DXgA_KCR.js";import{u as j}from"./use-merged-state-BDx2SpxW.js";import{f as _}from"./format-length-B-p6aW7q.js";const Ie=X({name:"NDrawerContent",inheritAttrs:!1,props:{blockScroll:Boolean,show:{type:Boolean,default:void 0},displayDirective:{type:String,required:!0},placement:{type:String,required:!0},contentClass:String,contentStyle:[Object,String],nativeScrollbar:{type:Boolean,required:!0},scrollbarProps:Object,trapFocus:{type:Boolean,default:!0},autoFocus:{type:Boolean,default:!0},showMask:{type:[Boolean,String],required:!0},maxWidth:Number,maxHeight:Number,minWidth:Number,minHeight:Number,resizable:Boolean,onClickoutside:Function,onAfterLeave:Function,onAfterEnter:Function,onEsc:Function},setup(e){const o=B(!!e.show),t=B(null),w=ve(V);let m=0,x="",f=null;const y=B(!1),v=B(!1),C=p(()=>e.placement==="top"||e.placement==="bottom"),{mergedClsPrefixRef:T,mergedRtlRef:I}=K(e),O=ge("Drawer",I,T),E=r,W=n=>{v.value=!0,m=C.value?n.clientY:n.clientX,x=document.body.style.cursor,document.body.style.cursor=C.value?"ns-resize":"ew-resize",document.body.addEventListener("mousemove",b),document.body.addEventListener("mouseleave",E),document.body.addEventListener("mouseup",r)},R=()=>{f!==null&&(window.clearTimeout(f),f=null),v.value?y.value=!0:f=window.setTimeout(()=>{y.value=!0},300)},D=()=>{f!==null&&(window.clearTimeout(f),f=null),y.value=!1},{doUpdateHeight:A,doUpdateWidth:U}=w,k=n=>{const{maxWidth:s}=e;if(s&&n>s)return s;const{minWidth:d}=e;return d&&n<d?d:n},F=n=>{const{maxHeight:s}=e;if(s&&n>s)return s;const{minHeight:d}=e;return d&&n<d?d:n};function b(n){var s,d;if(v.value)if(C.value){let h=((s=t.value)===null||s===void 0?void 0:s.offsetHeight)||0;const z=m-n.clientY;h+=e.placement==="bottom"?z:-z,h=F(h),A(h),m=n.clientY}else{let h=((d=t.value)===null||d===void 0?void 0:d.offsetWidth)||0;const z=m-n.clientX;h+=e.placement==="right"?z:-z,h=k(h),U(h),m=n.clientX}}function r(){v.value&&(m=0,v.value=!1,document.body.style.cursor=x,document.body.removeEventListener("mousemove",b),document.body.removeEventListener("mouseup",r),document.body.removeEventListener("mouseleave",E))}pe(()=>{e.show&&(o.value=!0)}),we(()=>e.show,n=>{n||r()}),ye(()=>{r()});const a=p(()=>{const{show:n}=e,s=[[L,n]];return e.showMask||s.push([ze,e.onClickoutside,void 0,{capture:!0}]),s});function l(){var n;o.value=!1,(n=e.onAfterLeave)===null||n===void 0||n.call(e)}return $e(p(()=>e.blockScroll&&o.value)),H(Se,t),H(xe,null),H(Be,null),{bodyRef:t,rtlEnabled:O,mergedClsPrefix:w.mergedClsPrefixRef,isMounted:w.isMountedRef,mergedTheme:w.mergedThemeRef,displayed:o,transitionName:p(()=>({right:"slide-in-from-right-transition",left:"slide-in-from-left-transition",top:"slide-in-from-top-transition",bottom:"slide-in-from-bottom-transition"})[e.placement]),handleAfterLeave:l,bodyDirectives:a,handleMousedownResizeTrigger:W,handleMouseenterResizeTrigger:R,handleMouseleaveResizeTrigger:D,isDragging:v,isHoverOnResizeTrigger:y}},render(){const{$slots:e,mergedClsPrefix:o}=this;return this.displayDirective==="show"||this.displayed||this.show?P(u("div",{role:"none"},u(fe,{disabled:!this.showMask||!this.trapFocus,active:this.show,autoFocus:this.autoFocus,onEsc:this.onEsc},{default:()=>u(Y,{name:this.transitionName,appear:this.isMounted,onAfterEnter:this.onAfterEnter,onAfterLeave:this.handleAfterLeave},{default:()=>P(u("div",me(this.$attrs,{role:"dialog",ref:"bodyRef","aria-modal":"true",class:[`${o}-drawer`,this.rtlEnabled&&`${o}-drawer--rtl`,`${o}-drawer--${this.placement}-placement`,this.isDragging&&`${o}-drawer--unselectable`,this.nativeScrollbar&&`${o}-drawer--native-scrollbar`]}),[this.resizable?u("div",{class:[`${o}-drawer__resize-trigger`,(this.isDragging||this.isHoverOnResizeTrigger)&&`${o}-drawer__resize-trigger--hover`],onMouseenter:this.handleMouseenterResizeTrigger,onMouseleave:this.handleMouseleaveResizeTrigger,onMousedown:this.handleMousedownResizeTrigger}):null,this.nativeScrollbar?u("div",{class:[`${o}-drawer-content-wrapper`,this.contentClass],style:this.contentStyle,role:"none"},e):u(be,Object.assign({},this.scrollbarProps,{contentStyle:this.contentStyle,contentClass:[`${o}-drawer-content-wrapper`,this.contentClass],theme:this.mergedTheme.peers.Scrollbar,themeOverrides:this.mergedTheme.peerOverrides.Scrollbar}),e)]),this.bodyDirectives)})})),[[L,this.displayDirective==="if"||this.displayed||this.show]]):null}}),{cubicBezierEaseIn:Oe,cubicBezierEaseOut:We}=M;function De({duration:e="0.3s",leaveDuration:o="0.2s",name:t="slide-in-from-bottom"}={}){return[i(`&.${t}-transition-leave-active`,{transition:`transform ${o} ${Oe}`}),i(`&.${t}-transition-enter-active`,{transition:`transform ${e} ${We}`}),i(`&.${t}-transition-enter-to`,{transform:"translateY(0)"}),i(`&.${t}-transition-enter-from`,{transform:"translateY(100%)"}),i(`&.${t}-transition-leave-from`,{transform:"translateY(0)"}),i(`&.${t}-transition-leave-to`,{transform:"translateY(100%)"})]}const{cubicBezierEaseIn:Ae,cubicBezierEaseOut:Ue}=M;function Pe({duration:e="0.3s",leaveDuration:o="0.2s",name:t="slide-in-from-left"}={}){return[i(`&.${t}-transition-leave-active`,{transition:`transform ${o} ${Ae}`}),i(`&.${t}-transition-enter-active`,{transition:`transform ${e} ${Ue}`}),i(`&.${t}-transition-enter-to`,{transform:"translateX(0)"}),i(`&.${t}-transition-enter-from`,{transform:"translateX(-100%)"}),i(`&.${t}-transition-leave-from`,{transform:"translateX(0)"}),i(`&.${t}-transition-leave-to`,{transform:"translateX(-100%)"})]}const{cubicBezierEaseIn:Le,cubicBezierEaseOut:Ne}=M;function je({duration:e="0.3s",leaveDuration:o="0.2s",name:t="slide-in-from-right"}={}){return[i(`&.${t}-transition-leave-active`,{transition:`transform ${o} ${Le}`}),i(`&.${t}-transition-enter-active`,{transition:`transform ${e} ${Ne}`}),i(`&.${t}-transition-enter-to`,{transform:"translateX(0)"}),i(`&.${t}-transition-enter-from`,{transform:"translateX(100%)"}),i(`&.${t}-transition-leave-from`,{transform:"translateX(0)"}),i(`&.${t}-transition-leave-to`,{transform:"translateX(100%)"})]}const{cubicBezierEaseIn:_e,cubicBezierEaseOut:Xe}=M;function Ye({duration:e="0.3s",leaveDuration:o="0.2s",name:t="slide-in-from-top"}={}){return[i(`&.${t}-transition-leave-active`,{transition:`transform ${o} ${_e}`}),i(`&.${t}-transition-enter-active`,{transition:`transform ${e} ${Xe}`}),i(`&.${t}-transition-enter-to`,{transform:"translateY(0)"}),i(`&.${t}-transition-enter-from`,{transform:"translateY(-100%)"}),i(`&.${t}-transition-leave-from`,{transform:"translateY(0)"}),i(`&.${t}-transition-leave-to`,{transform:"translateY(-100%)"})]}const Ke=i([c("drawer",`
 word-break: break-word;
 line-height: var(--n-line-height);
 position: absolute;
 pointer-events: all;
 box-shadow: var(--n-box-shadow);
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 background-color: var(--n-color);
 color: var(--n-text-color);
 box-sizing: border-box;
 `,[je(),Pe(),Ye(),De(),g("unselectable",`
 user-select: none; 
 -webkit-user-select: none;
 `),g("native-scrollbar",[c("drawer-content-wrapper",`
 overflow: auto;
 height: 100%;
 `)]),$("resize-trigger",`
 position: absolute;
 background-color: #0000;
 transition: background-color .3s var(--n-bezier);
 `,[g("hover",`
 background-color: var(--n-resize-trigger-color-hover);
 `)]),c("drawer-content-wrapper",`
 box-sizing: border-box;
 `),c("drawer-content",`
 height: 100%;
 display: flex;
 flex-direction: column;
 `,[g("native-scrollbar",[c("drawer-body-content-wrapper",`
 height: 100%;
 overflow: auto;
 `)]),c("drawer-body",`
 flex: 1 0 0;
 overflow: hidden;
 `),c("drawer-body-content-wrapper",`
 box-sizing: border-box;
 padding: var(--n-body-padding);
 `),c("drawer-header",`
 font-weight: var(--n-title-font-weight);
 line-height: 1;
 font-size: var(--n-title-font-size);
 color: var(--n-title-text-color);
 padding: var(--n-header-padding);
 transition: border .3s var(--n-bezier);
 border-bottom: 1px solid var(--n-divider-color);
 border-bottom: var(--n-header-border-bottom);
 display: flex;
 justify-content: space-between;
 align-items: center;
 `,[$("main",`
 flex: 1;
 `),$("close",`
 margin-left: 6px;
 transition:
 background-color .3s var(--n-bezier),
 color .3s var(--n-bezier);
 `)]),c("drawer-footer",`
 display: flex;
 justify-content: flex-end;
 border-top: var(--n-footer-border-top);
 transition: border .3s var(--n-bezier);
 padding: var(--n-footer-padding);
 `)]),g("right-placement",`
 top: 0;
 bottom: 0;
 right: 0;
 border-top-left-radius: var(--n-border-radius);
 border-bottom-left-radius: var(--n-border-radius);
 `,[$("resize-trigger",`
 width: 3px;
 height: 100%;
 top: 0;
 left: 0;
 transform: translateX(-1.5px);
 cursor: ew-resize;
 `)]),g("left-placement",`
 top: 0;
 bottom: 0;
 left: 0;
 border-top-right-radius: var(--n-border-radius);
 border-bottom-right-radius: var(--n-border-radius);
 `,[$("resize-trigger",`
 width: 3px;
 height: 100%;
 top: 0;
 right: 0;
 transform: translateX(1.5px);
 cursor: ew-resize;
 `)]),g("top-placement",`
 top: 0;
 left: 0;
 right: 0;
 border-bottom-left-radius: var(--n-border-radius);
 border-bottom-right-radius: var(--n-border-radius);
 `,[$("resize-trigger",`
 width: 100%;
 height: 3px;
 bottom: 0;
 left: 0;
 transform: translateY(1.5px);
 cursor: ns-resize;
 `)]),g("bottom-placement",`
 left: 0;
 bottom: 0;
 right: 0;
 border-top-left-radius: var(--n-border-radius);
 border-top-right-radius: var(--n-border-radius);
 `,[$("resize-trigger",`
 width: 100%;
 height: 3px;
 top: 0;
 left: 0;
 transform: translateY(-1.5px);
 cursor: ns-resize;
 `)])]),i("body",[i(">",[c("drawer-container",`
 position: fixed;
 `)])]),c("drawer-container",`
 position: relative;
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 pointer-events: none;
 `,[i("> *",`
 pointer-events: all;
 `)]),c("drawer-mask",`
 background-color: rgba(0, 0, 0, .3);
 position: absolute;
 left: 0;
 right: 0;
 top: 0;
 bottom: 0;
 `,[g("invisible",`
 background-color: rgba(0, 0, 0, 0)
 `),Ce({enterDuration:"0.2s",leaveDuration:"0.2s",enterCubicBezier:"var(--n-bezier-in)",leaveCubicBezier:"var(--n-bezier-out)"})])]),Ve=Object.assign(Object.assign({},q.props),{show:Boolean,width:[Number,String],height:[Number,String],placement:{type:String,default:"right"},maskClosable:{type:Boolean,default:!0},showMask:{type:[Boolean,String],default:!0},to:[String,Object],displayDirective:{type:String,default:"if"},nativeScrollbar:{type:Boolean,default:!0},zIndex:Number,onMaskClick:Function,scrollbarProps:Object,contentClass:String,contentStyle:[Object,String],trapFocus:{type:Boolean,default:!0},onEsc:Function,autoFocus:{type:Boolean,default:!0},closeOnEsc:{type:Boolean,default:!0},blockScroll:{type:Boolean,default:!0},maxWidth:Number,maxHeight:Number,minWidth:Number,minHeight:Number,resizable:Boolean,defaultWidth:{type:[Number,String],default:251},defaultHeight:{type:[Number,String],default:251},onUpdateWidth:[Function,Array],onUpdateHeight:[Function,Array],"onUpdate:width":[Function,Array],"onUpdate:height":[Function,Array],"onUpdate:show":[Function,Array],onUpdateShow:[Function,Array],onAfterEnter:Function,onAfterLeave:Function,drawerStyle:[String,Object],drawerClass:String,target:null,onShow:Function,onHide:Function}),Qe=X({name:"Drawer",inheritAttrs:!1,props:Ve,setup(e){const{mergedClsPrefixRef:o,namespaceRef:t,inlineThemeDisabled:w}=K(e),m=Re(),x=q("Drawer","-drawer",Ke,Te,e,o),f=B(e.defaultWidth),y=B(e.defaultHeight),v=j(N(e,"width"),f),C=j(N(e,"height"),y),T=p(()=>{const{placement:r}=e;return r==="top"||r==="bottom"?"":_(v.value)}),I=p(()=>{const{placement:r}=e;return r==="left"||r==="right"?"":_(C.value)}),O=r=>{const{onUpdateWidth:a,"onUpdate:width":l}=e;a&&S(a,r),l&&S(l,r),f.value=r},E=r=>{const{onUpdateHeight:a,"onUpdate:width":l}=e;a&&S(a,r),l&&S(l,r),y.value=r},W=p(()=>[{width:T.value,height:I.value},e.drawerStyle||""]);function R(r){const{onMaskClick:a,maskClosable:l}=e;l&&k(!1),a&&a(r)}function D(r){R(r)}const A=Fe();function U(r){var a;(a=e.onEsc)===null||a===void 0||a.call(e),e.show&&e.closeOnEsc&&Me(r)&&(A.value||k(!1))}function k(r){const{onHide:a,onUpdateShow:l,"onUpdate:show":n}=e;l&&S(l,r),n&&S(n,r),a&&!r&&S(a,r)}H(V,{isMountedRef:m,mergedThemeRef:x,mergedClsPrefixRef:o,doUpdateShow:k,doUpdateHeight:E,doUpdateWidth:O});const F=p(()=>{const{common:{cubicBezierEaseInOut:r,cubicBezierEaseIn:a,cubicBezierEaseOut:l},self:{color:n,textColor:s,boxShadow:d,lineHeight:h,headerPadding:z,footerPadding:G,borderRadius:J,bodyPadding:Q,titleFontSize:Z,titleTextColor:ee,titleFontWeight:te,headerBorderBottom:re,footerBorderTop:oe,closeIconColor:ne,closeIconColorHover:ie,closeIconColorPressed:ae,closeColorHover:se,closeColorPressed:le,closeIconSize:de,closeSize:ce,closeBorderRadius:ue,resizableTriggerColorHover:he}}=x.value;return{"--n-line-height":h,"--n-color":n,"--n-border-radius":J,"--n-text-color":s,"--n-box-shadow":d,"--n-bezier":r,"--n-bezier-out":l,"--n-bezier-in":a,"--n-header-padding":z,"--n-body-padding":Q,"--n-footer-padding":G,"--n-title-text-color":ee,"--n-title-font-size":Z,"--n-title-font-weight":te,"--n-header-border-bottom":re,"--n-footer-border-top":oe,"--n-close-icon-color":ne,"--n-close-icon-color-hover":ie,"--n-close-icon-color-pressed":ae,"--n-close-size":ce,"--n-close-color-hover":se,"--n-close-color-pressed":le,"--n-close-icon-size":de,"--n-close-border-radius":ue,"--n-resize-trigger-color-hover":he}}),b=w?He("drawer",void 0,F,e):void 0;return{mergedClsPrefix:o,namespace:t,mergedBodyStyle:W,handleOutsideClick:D,handleMaskClick:R,handleEsc:U,mergedTheme:x,cssVars:w?void 0:F,themeClass:b==null?void 0:b.themeClass,onRender:b==null?void 0:b.onRender,isMounted:m}},render(){const{mergedClsPrefix:e}=this;return u(Ee,{to:this.to,show:this.show},{default:()=>{var o;return(o=this.onRender)===null||o===void 0||o.call(this),P(u("div",{class:[`${e}-drawer-container`,this.namespace,this.themeClass],style:this.cssVars,role:"none"},this.showMask?u(Y,{name:"fade-in-transition",appear:this.isMounted},{default:()=>this.show?u("div",{"aria-hidden":!0,class:[`${e}-drawer-mask`,this.showMask==="transparent"&&`${e}-drawer-mask--invisible`],onClick:this.handleMaskClick}):null}):null,u(Ie,Object.assign({},this.$attrs,{class:[this.drawerClass,this.$attrs.class],style:[this.mergedBodyStyle,this.$attrs.style],blockScroll:this.blockScroll,contentStyle:this.contentStyle,contentClass:this.contentClass,placement:this.placement,scrollbarProps:this.scrollbarProps,show:this.show,displayDirective:this.displayDirective,nativeScrollbar:this.nativeScrollbar,onAfterEnter:this.onAfterEnter,onAfterLeave:this.onAfterLeave,trapFocus:this.trapFocus,autoFocus:this.autoFocus,resizable:this.resizable,maxHeight:this.maxHeight,minHeight:this.minHeight,maxWidth:this.maxWidth,minWidth:this.minWidth,showMask:this.showMask,onEsc:this.handleEsc,onClickoutside:this.handleOutsideClick}),this.$slots)),[[ke,{zIndex:this.zIndex,enabled:this.show}]])}})}});export{Qe as _};
