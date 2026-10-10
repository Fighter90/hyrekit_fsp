import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ArenaBoard } from '../api/types'
import { formatClock } from '../lib/arena'
import { Leaderboard, VerdictChip } from '../components/arena/parts'

const board: ArenaBoard = {
  round_id: 'r1',
  problems: [
    { code: 'sum-multiples', title: 'Сумма кратных', level: 1, level_title: 'Базовый', topic: 'математика' },
    { code: 'brackets', title: 'Скобки', level: 2, level_title: 'Средний', topic: 'стек' },
  ],
  frozen: true,
  frozen_since: '2026-10-10T10:30:00Z',
  version: 'v1',
  server_time: '2026-10-10T10:40:00Z',
  rows: [
    {
      rank: 1, participant_id: 'p1', profile_id: 'c1', name: 'Участник #A1B2', me: false, category_title: 'Backend',
      solved: 2, penalty: 37, suspicious: true, arena_rating: 1580, active: true, invitation_status: null,
      cells: { 'sum-multiples': { solved: true, attempts: 1, minute: 5 }, brackets: { solved: true, attempts: 0, minute: 12 } },
    },
    {
      rank: 2, participant_id: 'p2', profile_id: null, name: 'Иван', me: true, category_title: null,
      solved: 0, penalty: 0, suspicious: false, arena_rating: null, active: true,
      cells: { brackets: { solved: false, attempts: 2, minute: 0 } },
    },
  ],
}

describe('Code Arena', () => {
  it('форматирует таймер раунда', () => {
    expect(formatClock(65)).toBe('01:05')
    expect(formatClock(3725)).toBe('1:02:05')
    expect(formatClock(-3)).toBe('00:00')
  })

  it('показывает вердикт и ожидание проверки', () => {
    const { rerender } = render(<VerdictChip verdict="OK" />)
    expect(screen.getByText('OK')).toHaveClass('verdict--ok')
    rerender(<VerdictChip verdict="TLE" />)
    expect(screen.getByTitle('Превышено время')).toHaveClass('verdict--bad')
    rerender(<VerdictChip verdict={null} />)
    expect(screen.getByText('Проверяется')).toBeInTheDocument()
  })

  it('рисует таблицу ICPC: заморозка, попытки, своя строка, приглашение', () => {
    const onInvite = vi.fn()
    render(
      <MemoryRouter>
        <Leaderboard board={board} onInvite={onInvite} />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Таблица заморожена/)).toBeInTheDocument()
    expect(screen.getByText('+1')).toHaveClass('cell-ok')
    expect(screen.getByText('−2')).toHaveClass('cell-bad')
    expect(screen.getByText('вы').closest('tr')).toHaveClass('is-me')
    expect(screen.getByTitle(/почти совпадает/)).toBeInTheDocument()
    const buttons = screen.getAllByRole('button', { name: 'Пригласить' })
    expect(buttons).toHaveLength(1) // у анонимного без профиля кнопки нет
    fireEvent.click(buttons[0])
    expect(onInvite).toHaveBeenCalledWith(board.rows[0])
  })
})
