import { useState } from 'react';
import type { FormEvent } from 'react';
import jsonData from '../../BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json';

interface HourInput {
  hour: number;
  demand_kwh: number;
  solar_kwh: number;
  tariff_bdt_per_kwh: number;
}

interface BatteryInput {
  capacity_kwh: number;
  initial_energy_kwh: number;
  minimum_energy_kwh: number;
  max_charge_kwh_per_hour: number;
  max_discharge_kwh_per_hour: number;
}

interface CaseInput {
  scenario_id: string;
  operator_notes: string[];
  hours: HourInput[];
  battery: BatteryInput;
}

interface DirectiveInterpretation {
  note_index: number;
  applies: boolean;
  directive_type: string;
  explanation: string;
}

interface HourlyPlan {
  hour: number;
  grid_kwh: number;
  solar_used_kwh: number;
  battery_action: string;
  battery_kwh: number;
  battery_energy_after_kwh: number;
}

interface ExpectedOutput {
  directive_interpretation: DirectiveInterpretation[];
  hourly_plan: HourlyPlan[];
  total_grid_kwh: number;
  total_cost_bdt: number;
  peak_grid_kwh: number;
  plan_summary: string;
}

interface SampleData {
  id?: string;
  sample_id?: string;
  label?: string;
  rationale?: string;
  input?: CaseInput;
  expected_output?: ExpectedOutput;
  [key: string]: unknown;
}

interface JsonDataType {
  cases?: SampleData[];
  samples?: SampleData[];
  [key: string]: unknown;
}

export default function SampleViewer() {
  const [searchInput, setSearchInput] = useState('');
  const [selectedSample, setSelectedSample] = useState<SampleData | null>(null);

  const normalizeSampleId = (rawInput: string) => {
    const digits = rawInput.replace(/\D/g, ''); 
    if (!digits) return '';
    return `SAMPLE-${digits.padStart(2, '0')}`;
  };

  const handleSearch = (e: FormEvent) => {
    e.preventDefault();
    const targetKey = normalizeSampleId(searchInput);
    
    const data = jsonData as JsonDataType;
    const arrayData = data.cases || data.samples || data;

    if (Array.isArray(arrayData)) {
      const match = arrayData.find((item: SampleData) => {
        const itemId = normalizeSampleId(item.id || item.sample_id || '');
        return itemId === targetKey;
      });
      setSelectedSample(match || null);
    } else {
      const mapData = arrayData as Record<string, SampleData>;
      setSelectedSample(mapData[targetKey] || null);
    }
  };

  const formatHour = (hour: number) => {
    if (hour === 0) return '12 AM';
    if (hour === 12) return '12 PM';
    return hour > 12 ? `${hour - 12} PM` : `${hour} AM`;
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui, -apple-system, sans-serif', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '30px' }}>
        <h1 style={{ color: '#2c3e50' }}>GridWise Energy Dashboard</h1>
        <form onSubmit={handleSearch} style={{ display: 'flex', justifyContent: 'center', gap: '10px' }}>
          <input
            type="text"
            placeholder="Enter Sample ID (e.g. 1 or SAMPLE-01)"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ padding: '10px', fontSize: '16px', width: '300px', borderRadius: '5px', border: '1px solid #ccc' }}
          />
          <button type="submit" style={{ padding: '10px 20px', fontSize: '16px', borderRadius: '5px', border: 'none', background: '#3498db', color: 'white', cursor: 'pointer' }}>
            Load Scenario
          </button>
        </form>
      </div>

      <hr style={{ border: 'none', borderTop: '1px solid #eee', marginBottom: '30px' }} />

      {selectedSample && selectedSample.input && selectedSample.expected_output ? (
        <div>
          <div style={{ marginBottom: '20px', padding: '20px', background: '#f8f9fa', borderRadius: '8px', borderLeft: '5px solid #3498db' }}>
            <h2 style={{ margin: '0 0 10px 0', color: '#2c3e50' }}>{selectedSample.label}</h2>
            <p style={{ margin: '0', color: '#555' }}><strong>Rationale:</strong> {selectedSample.rationale}</p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '30px' }}>
            {/* Operator Notes */}
            <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
              <h3 style={{ marginTop: 0, color: '#e67e22' }}>📝 Operator Notes</h3>
              <ul style={{ paddingLeft: '20px', margin: 0 }}>
                {selectedSample.input.operator_notes.map((note, idx) => (
                  <li key={idx} style={{ marginBottom: '10px', lineHeight: '1.5' }}>{note}</li>
                ))}
              </ul>
            </div>

            {/* Battery Profile */}
            <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
              <h3 style={{ marginTop: 0, color: '#27ae60' }}>🔋 Battery Specifications</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div><strong>Capacity:</strong> {selectedSample.input.battery.capacity_kwh} kWh</div>
                <div><strong>Initial Energy:</strong> {selectedSample.input.battery.initial_energy_kwh} kWh</div>
                <div><strong>Minimum Reserve:</strong> {selectedSample.input.battery.minimum_energy_kwh} kWh</div>
                <div><strong>Max Charge Rate:</strong> {selectedSample.input.battery.max_charge_kwh_per_hour} kW</div>
                <div><strong>Max Discharge Rate:</strong> {selectedSample.input.battery.max_discharge_kwh_per_hour} kW</div>
              </div>
            </div>
          </div>

          <h2 style={{ color: '#2c3e50', borderBottom: '2px solid #3498db', paddingBottom: '10px' }}>AI Insights & Execution Plan</h2>
          
          <div style={{ marginBottom: '30px', padding: '20px', background: '#f4f6f7', borderRadius: '8px' }}>
            <h3 style={{ marginTop: 0, color: '#2980b9' }}>🤖 How the AI Interpreted the Notes</h3>
            {selectedSample.expected_output.directive_interpretation.map((interp, idx) => (
              <div key={idx} style={{ marginBottom: '10px', padding: '10px', background: 'white', borderRadius: '5px', borderLeft: interp.applies ? '4px solid #27ae60' : '4px solid #95a5a6' }}>
                <strong>Note {interp.note_index + 1}:</strong> {interp.explanation}
                <span style={{ marginLeft: '10px', fontSize: '12px', padding: '3px 8px', borderRadius: '12px', background: interp.applies ? '#e8f8f5' : '#f2f4f4', color: interp.applies ? '#1abc9c' : '#7f8c8d' }}>
                  {interp.directive_type}
                </span>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '30px' }}>
            <div style={{ padding: '20px', textAlign: 'center', background: '#fff3e0', borderRadius: '8px', border: '1px solid #ffe0b2' }}>
              <h4 style={{ margin: '0 0 10px 0', color: '#e65100' }}>Total Cost</h4>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#e65100' }}>৳ {selectedSample.expected_output.total_cost_bdt}</div>
            </div>
            <div style={{ padding: '20px', textAlign: 'center', background: '#e3f2fd', borderRadius: '8px', border: '1px solid #bbdefb' }}>
              <h4 style={{ margin: '0 0 10px 0', color: '#1565c0' }}>Total Grid Usage</h4>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1565c0' }}>{selectedSample.expected_output.total_grid_kwh} kWh</div>
            </div>
            <div style={{ padding: '20px', textAlign: 'center', background: '#fce4ec', borderRadius: '8px', border: '1px solid #f8bbd0' }}>
              <h4 style={{ margin: '0 0 10px 0', color: '#c2185b' }}>Peak Grid Demand</h4>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#c2185b' }}>{selectedSample.expected_output.peak_grid_kwh} kWh</div>
            </div>
          </div>

          <div style={{ marginBottom: '30px', padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
            <h3 style={{ marginTop: 0 }}>📊 Strategy Summary</h3>
            <p style={{ margin: 0, lineHeight: '1.6' }}>{selectedSample.expected_output.plan_summary}</p>
          </div>

          <h3 style={{ color: '#2c3e50' }}>⏱️ 24-Hour Operational Schedule</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: '#f1f2f6', color: '#2f3542' }}>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea' }}>Time</th>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea' }}>Energy Demand</th>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea' }}>Available Solar</th>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea' }}>Grid Tariff (৳)</th>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea', background: '#eccc68' }}>Grid Drawn</th>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea', background: '#7bed9f' }}>Solar Used</th>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea', background: '#70a1ff', color: 'white' }}>Battery Action</th>
                  <th style={{ padding: '12px', borderBottom: '2px solid #dfe4ea', background: '#70a1ff', color: 'white' }}>Battery Level</th>
                </tr>
              </thead>
              <tbody>
                {selectedSample.input.hours.map((hourInput) => {
                  const hourOutput = selectedSample.expected_output?.hourly_plan.find(p => p.hour === hourInput.hour);
                  return (
                    <tr key={hourInput.hour} style={{ borderBottom: '1px solid #f1f2f6' }}>
                      <td style={{ padding: '10px', fontWeight: 'bold' }}>{formatHour(hourInput.hour)}</td>
                      <td style={{ padding: '10px' }}>{hourInput.demand_kwh} kWh</td>
                      <td style={{ padding: '10px', color: '#d35400' }}>{hourInput.solar_kwh} kWh</td>
                      <td style={{ padding: '10px' }}>৳ {hourInput.tariff_bdt_per_kwh}</td>
                      <td style={{ padding: '10px', fontWeight: 'bold', color: '#c0392b' }}>{hourOutput?.grid_kwh} kWh</td>
                      <td style={{ padding: '10px', fontWeight: 'bold', color: '#27ae60' }}>{hourOutput?.solar_used_kwh} kWh</td>
                      <td style={{ padding: '10px' }}>
                        <span style={{ 
                          padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 'bold',
                          background: hourOutput?.battery_action === 'charge' ? '#dff9fb' : hourOutput?.battery_action === 'discharge' ? '#f5f6fa' : '#f1f2f6',
                          color: hourOutput?.battery_action === 'charge' ? '#2980b9' : hourOutput?.battery_action === 'discharge' ? '#e67e22' : '#7f8c8d'
                        }}>
                          {hourOutput?.battery_action.toUpperCase()} {hourOutput?.battery_kwh ? `(${hourOutput.battery_kwh} kWh)` : ''}
                        </span>
                      </td>
                      <td style={{ padding: '10px', fontWeight: 'bold', color: '#2980b9' }}>{hourOutput?.battery_energy_after_kwh} kWh</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', color: '#7f8c8d', marginTop: '50px' }}>
          <p>No scenario loaded. Enter a sample ID (e.g., "1" or "02") and click Load Scenario.</p>
        </div>
      )}
    </div>
  );
}