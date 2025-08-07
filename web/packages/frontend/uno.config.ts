import { defineConfig, presetAttributify, presetWind3 } from 'unocss'

export default defineConfig({
  presets: [presetAttributify(), presetWind3()],
  shortcuts: {},
  theme: {},
  rules: [
    [
      /^paint-order-(\w+)$/,
      ([, w]) => ({
        'paint-order': {
          fsm: 'fill stroke markers',
          fms: 'fill markers stroke',
          sfm: 'stroke fill markers',
          smf: 'stroke markers fill',
          mfs: 'markers fill stroke',
          msf: 'markers stroke fill',
        }[w],
      }),
    ],
  ],
})
