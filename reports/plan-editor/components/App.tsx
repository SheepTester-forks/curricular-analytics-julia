/** @jsxImportSource preact */
/// <reference no-default-lib="true"/>
/// <reference lib="dom" />
/// <reference lib="deno.ns" />

import { useState } from 'preact/hooks'
import { Prereqs } from '../../util/Prereqs.ts'
import { AcademicPlan } from '../types.ts'
import { Editor } from './Editor.tsx'
import { PrereqSidebar } from './PrereqSidebar.tsx'

export type AppProps = {
  prereqs: Prereqs
  initPlan: AcademicPlan
  mode: 'student' | 'advisor'
}
export function App ({ prereqs: initPrereqs, initPlan, mode }: AppProps) {
  const [plan, setPlan] = useState(initPlan)
  const [customPrereqs, setCustomPrereqs] = useState<Prereqs>({})

  const prereqs = { ...initPrereqs, ...customPrereqs }

  return (
    <>
      <main class='main'>
        <div class='info'>
          <input
            class='plan-name'
            type='text'
            placeholder='Plan name'
            aria-label='Plan name'
            value={plan.name}
            onInput={e => setPlan({ ...plan, name: e.currentTarget.value })}
          />
          <span class='total-units plan-units'>
            Total units:{' '}
            <span class='units'>
              {plan.years.reduce(
                (cum, curr) =>
                  cum +
                  curr.reduce(
                    (cum, curr) =>
                      cum + curr.reduce((cum, curr) => cum + +curr.units, 0),
                    0
                  ),
                0
              )}
            </span>
          </span>
        </div>
        <Editor plan={plan} onPlan={setPlan} />
      </main>
      <PrereqSidebar
        prereqs={prereqs}
        onPrereqs={setCustomPrereqs}
        plan={plan}
        mode={mode}
      />
      <datalist id='courses'>
        {Object.keys(prereqs).map(code => (
          <option value={code} key={code} />
        ))}
      </datalist>
    </>
  )
}