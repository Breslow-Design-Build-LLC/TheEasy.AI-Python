import os
from openai import OpenAI
import json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

prompts = {
    'gate1': ('pmpt_698fd0bd177881908e6155c75caf5051054f971f90c1739f', {'product_options': 'A) R-Blade\nB) R-Breeze\nC) K-Bana\nD) X-Blast\nE) Sky-Tilt\nF) Kitchens'}),
    'gate2': ('pmpt_698f24734b2c8190b35dbd645766daba0a00ac37516c9940', {'dimension_context': '{}'}),
    'gate2b': ('pmpt_698f2e84a3a4819692fe9ba63dacfe53057c8a385232b3fd', {'orientation_context': '{}'}),
    'gate3': ('pmpt_698f31a4830881958384594286c8c62f06c5a37e85bd4e6b', {'bay_logic_context': '{}'}),
    'gate3b': ('pmpt_698f91233a908193a38530bfc21a5ea307ff467d4352a6c4', {'threshold_advisory_context': '{}'}),
    'gate3c': ('pmpt_698f91f15ed08193bf26b49690cf731a01f60e94ff8b9467', {'dimension_router_context': '{}'}),
    'gate4': ('pmpt_698f9431c0b08193a0c301c4f992a374057cb68b291d43d1', {'base_pricing_context': '{}'}),
    'gate4b': ('pmpt_698f94944ccc81908e741633ae70e04700504d135e320e91', {'structural_addons_context': '{}'}),
    'gate5': ('pmpt_698f956ab9388194beaaf3c010f9ecba083af44f00bcb344', {'finish_surcharge_context': '{}'}),
    'gate6': ('pmpt_698f96f15f748196bf6c1a302cad209a069bfe999f2a5f54', {'lighting_fans_context': '{}'}),
    'gate7': ('pmpt_698fc0af7d8481978eaea4b4f3c04f6106fb16b6264d6bfa', {'heater_context': '{}'}),
    'gate8': ('pmpt_698fc169fbac8190be759c4ef225d51e028f54ce31d56012', {'shades_privacy_context': '{}'}),
    'gate9': ('pmpt_698fc57649588193a608068866018bdc0d514a59130d9689', {'trim_context': '{}'}),
    'gate10': ('pmpt_698fc653c7888194b612a1cc0552cf510d2785432b170ae1', {'electrical_scope_context': '{}'}),
    'gate11': ('pmpt_698fc808ed68819483779236f399e4780f0556d31b05108f', {'installation_context': '{}'}),
    'gate12': ('pmpt_698fc8c63dec819795ac20deb6e6dc2e0b0ead22679c7725', {'services_context': '{}'}),
    'gate13': ('pmpt_698fc9a974548194ab73dd8b9de548a5041fa6cb9ee62f01', {'quote_summary_context': '{}'}),
    'gate14': ('pmpt_698fca776db0819397a781ca4f0cc09e0cbd2cff13cddf3c', {'audit_context': '{}'}),
    'gate15': ('pmpt_698fcae448608196b3a5af34e39543dd0d468eb0783e0095', {'final_payload_context': '{}'}),
    'gate16': ('pmpt_698fcc2efed481958d95da57eaf06a4800dd978861a335d5', {'breakdown_context': '{}'}),
    'gate17': ('pmpt_698fcd533ee88190a04d275ba6163e1b0a107019ab0c0e6d', {'revision_context': '{}'}),
    'gate18': ('pmpt_698fcdd1d558819690b1a1ec882cd2aa0c71bcba13f772ea', {'handoff_context': '{}'}),
}

results = {}
for name, (pid, variables) in prompts.items():
    print(f"Fetching {name}...")
    try:
        resp = client.responses.create(
            model="gpt-5.2",
            prompt={"id": pid, "variables": variables},
            input=[{"role": "user", "content": "hi"}],
            store=False,
        )
        dev_message = ""
        if resp.instructions:
            for msg in resp.instructions:
                if msg.role == "developer":
                    for part in msg.content:
                        if hasattr(part, 'text'):
                            dev_message += part.text
        results[name] = {
            "id": pid,
            "required_variables": list(variables.keys()),
            "developer_message": dev_message,
            "sample_output": resp.output_text
        }
        print(f"  OK - {len(dev_message)} chars")
    except Exception as e:
        results[name] = {"id": pid, "error": str(e)}
        print(f"  ERROR: {e}")

with open("prompts_export.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nDone! Saved {len(results)} prompts to prompts_export.json")
print(f"Successful: {sum(1 for v in results.values() if 'developer_message' in v)}")
print(f"Errors: {sum(1 for v in results.values() if 'error' in v)}")