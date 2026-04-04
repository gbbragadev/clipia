import Navbar from '@/components/Navbar'
import HeroSection from '@/components/hero/HeroSection'
import { WipeDivider, FilmstripDivider } from '@/components/SectionDivider'
import SocialProofBar from '@/components/SocialProofBar'
import ShowcaseSection from '@/components/ShowcaseSection'
import DemoSection from '@/components/demo/DemoSection'
import HowItWorks from '@/components/HowItWorks'
import WaitlistForm from '@/components/WaitlistForm'
import Footer from '@/components/Footer'

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <HeroSection />
        <WipeDivider />
        <SocialProofBar />
        <FilmstripDivider />
        <ShowcaseSection />
        <WipeDivider />
        <DemoSection />
        <WipeDivider />
        <HowItWorks />
        <FilmstripDivider />
        <WaitlistForm />
      </main>
      <Footer />
    </>
  )
}
