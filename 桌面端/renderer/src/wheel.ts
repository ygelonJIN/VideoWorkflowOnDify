/**
 * 滚轮归属：没进去打字的输入框不该吃掉滚轮。
 *
 * 指针停在 textarea 上时，浏览器默认滚的是 textarea 自己的内容——哪怕你根本没点进去。
 * 于是「原始需求」这种长输入会把滚轮全吃掉，抽屉本身滚不动，看起来像卡住。
 * 规则：只在输入框已经聚焦（真在里面打字）时才让它自己滚，否则把这段滚轮交给外层容器。
 */

function scrollableAncestor(from: HTMLElement): HTMLElement | null {
  let node = from.parentElement;
  while (node) {
    const style = getComputedStyle(node);
    const scrollable = style.overflowY === "auto" || style.overflowY === "scroll";
    if (scrollable && node.scrollHeight > node.clientHeight + 1) return node;
    node = node.parentElement;
  }
  return null;
}

export function installWheelRule(): () => void {
  const onWheel = (event: WheelEvent) => {
    const field = (event.target as HTMLElement | null)?.closest?.("textarea");
    // 聚焦中的输入框照常自己滚：那是"选中了再滚里面"
    if (!field || field === document.activeElement) return;
    const scroller = scrollableAncestor(field);
    if (!scroller) return;
    event.preventDefault();
    // deltaMode 1 是"行"，按一行约 16px 折算
    const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
    scroller.scrollTop += delta;
  };
  window.addEventListener("wheel", onWheel, { passive: false, capture: true });
  return () => window.removeEventListener("wheel", onWheel, { capture: true });
}
