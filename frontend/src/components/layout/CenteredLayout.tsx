import { Outlet } from 'react-router-dom'
import Logo from '../ui/Logo'
import GlyphStrip from '../ui/GlyphStrip'

export default function CenteredLayout() {
  return (
    <div className="centered">
      <div className="bg-grid" aria-hidden />
      <div className="centered__orb centered__orb--a" aria-hidden />
      <div className="centered__orb centered__orb--b" aria-hidden />
      <div className="centered__logo"><Logo /></div>
      <main className="centered__main">
        <Outlet />
      </main>
      <GlyphStrip className="centered__strip" speed={60} />
    </div>
  )
}
