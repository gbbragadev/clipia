import { Composition } from 'remotion'
import { ExampleShort } from './compositions/ExampleShort'

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ExampleShort"
        component={ExampleShort}
        durationInFrames={150}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          title: '5 fatos sobre o oceano',
          subtitle: 'Voce sabia que o oceano cobre mais de setenta por cento da Terra?',
          bgGradient: ['#1e1b4b', '#0c4a6e'] as [string, string],
        }}
      />
    </>
  )
}
