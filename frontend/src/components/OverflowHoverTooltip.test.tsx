import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import OverflowHoverTooltip from './OverflowHoverTooltip';

afterEach(() => {
  cleanup();
});

function mockOverflow(el: HTMLElement, overflowing: boolean) {
  Object.defineProperty(el, 'clientWidth', { configurable: true, value: 80 });
  Object.defineProperty(el, 'scrollWidth', { configurable: true, value: overflowing ? 240 : 80 });
  Object.defineProperty(el, 'clientHeight', { configurable: true, value: 20 });
  Object.defineProperty(el, 'scrollHeight', { configurable: true, value: overflowing ? 60 : 20 });
}

function renderTooltip(text: string, overflowing: boolean, label = 'chip') {
  const view = render(
    <div style={{ width: 96 }}>
      <OverflowHoverTooltip text={text} className="block min-w-0">
        <span className="truncate">{label}</span>
      </OverflowHoverTooltip>
    </div>,
  );
  const trigger = screen.getByTestId('overflow-tooltip-trigger');
  mockOverflow(trigger, overflowing);
  const inner = trigger.firstElementChild;
  if (inner instanceof HTMLElement) mockOverflow(inner, overflowing);
  return { ...view, trigger };
}

describe('OverflowHoverTooltip', () => {
  it('does not open for non-truncated text', () => {
    const { trigger } = renderTooltip('short', false);
    fireEvent.mouseEnter(trigger);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('opens on hover when text is truncated', () => {
    const { trigger } = renderTooltip('a very long diagnostic message', true);
    fireEvent.mouseEnter(trigger);
    expect(screen.getByRole('tooltip').textContent).toContain('a very long diagnostic message');
  });

  it('opens on keyboard focus and closes on Escape', () => {
    const { trigger } = renderTooltip('gemini-3.1-flash-image-preview-unbroken', true);
    trigger.focus();
    fireEvent.focus(trigger);
    expect(screen.getByRole('tooltip')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('closes on outside pointerdown', () => {
    const { trigger } = renderTooltip('outside dismiss', true);
    fireEvent.mouseEnter(trigger);
    expect(screen.getByRole('tooltip')).toBeTruthy();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('closes on pointer leave and blur', () => {
    const { trigger } = renderTooltip('leave me', true);
    fireEvent.mouseEnter(trigger);
    fireEvent.mouseLeave(trigger);
    expect(screen.queryByRole('tooltip')).toBeNull();
    fireEvent.focus(trigger);
    fireEvent.blur(trigger);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('keeps only one open tooltip across instances', () => {
    render(
      <div>
        <OverflowHoverTooltip text="first long status">
          <span>one</span>
        </OverflowHoverTooltip>
        <OverflowHoverTooltip text="second long status">
          <span>two</span>
        </OverflowHoverTooltip>
      </div>,
    );
    const triggers = screen.getAllByTestId('overflow-tooltip-trigger');
    mockOverflow(triggers[0], true);
    mockOverflow(triggers[1], true);
    fireEvent.mouseEnter(triggers[0]);
    fireEvent.mouseEnter(triggers[1]);
    const tips = screen.getAllByRole('tooltip');
    expect(tips).toHaveLength(1);
    expect(tips[0].textContent).toContain('second long status');
  });

  it('stays inside a narrow container and wraps long model names', () => {
    const name = 'google/gemini-3.1-flash-image-preview-extremely-long';
    const { trigger } = renderTooltip(name, true, name);
    fireEvent.mouseEnter(trigger);
    const tip = screen.getByTestId('overflow-tooltip');
    expect(tip.className).toContain('break-words');
    expect(tip.style.width).toBe('280px');
  });

  it('exposes an accessible tooltip role without a native title', () => {
    const { trigger } = renderTooltip('diagnostics chip', true, 'applied · visual QA');
    fireEvent.focus(trigger);
    const tip = screen.getByRole('tooltip');
    expect(trigger.getAttribute('aria-describedby')).toBe(tip.id);
    expect(trigger.getAttribute('title')).toBeNull();
  });

  it('toggles on non-mouse pointer up for touch fallback', () => {
    const { trigger } = renderTooltip('touch caption', true);
    fireEvent.pointerUp(trigger, { pointerType: 'touch' });
    expect(screen.getByRole('tooltip')).toBeTruthy();
    fireEvent.pointerUp(trigger, { pointerType: 'touch' });
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('does not open when tooltip text is empty', () => {
    const { trigger } = renderTooltip('   ', true, 'empty');
    fireEvent.mouseEnter(trigger);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });
});
