import { act,renderHook } from '@testing-library/react'
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { usePlayback } from '../hooks/usePlayback'
beforeEach(()=>vi.useFakeTimers({toFake:['setTimeout','clearTimeout','requestAnimationFrame','cancelAnimationFrame','performance']}))
afterEach(()=>vi.useRealTimers())
it('starts paused and does not advance while paused',()=>{const {result}=renderHook(()=>usePlayback(120));act(()=>vi.advanceTimersByTime(1000));expect(result.current.time).toBe(0);expect(result.current.playing).toBe(false)})
it('play advances time and pause freezes it',()=>{const {result}=renderHook(()=>usePlayback(120));act(()=>result.current.toggle());act(()=>vi.advanceTimersByTime(1000));expect(result.current.time).toBeGreaterThan(.5);act(()=>result.current.toggle());const time=result.current.time;act(()=>vi.advanceTimersByTime(1000));expect(result.current.time).toBe(time)})
it('scrubbing pauses playback and clamps bounds',()=>{const {result}=renderHook(()=>usePlayback(120));act(()=>result.current.toggle());act(()=>result.current.seek(52));expect(result.current.time).toBe(52);expect(result.current.playing).toBe(false);act(()=>result.current.seek(999));expect(result.current.time).toBe(120)})
it('restart returns to the observation window',()=>{const {result}=renderHook(()=>usePlayback(120));act(()=>result.current.seek(84));act(()=>result.current.restart());expect(result.current.time).toBe(0);expect(result.current.playing).toBe(false)})
it('reaching the end stops playback and play restarts it',()=>{const {result}=renderHook(()=>usePlayback(1));act(()=>result.current.toggle());act(()=>vi.advanceTimersByTime(2200));expect(result.current.time).toBe(1);expect(result.current.playing).toBe(false);act(()=>result.current.toggle());expect(result.current.time).toBe(0);expect(result.current.playing).toBe(true)})
