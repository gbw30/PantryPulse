import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-teal-800">PantryPulse · Simulated planning</p>
      <h1 className="mb-6 text-4xl font-semibold tracking-tight">Research-inspired resource allocation</h1>
      <p className="mb-6 leading-7">Compare classical goal programming and an EGP-PI-inspired model with simulated vulnerability attributes and absolute and relative deprivation goals.</p>
      <p className="mb-6 leading-7">The presenter workspace connects saved forecasts, frozen scenarios and independently verified comparisons. Results are simulations; no operational dispatch is performed.</p>
      <p className="mb-6"><Link className="font-medium text-teal-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4" href="/optimization">Open optimization workspace</Link></p>
      <a className="font-medium text-teal-800 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4" href="https://doi.org/10.1111/itor.70252">Rampazo et al. · September 11, 2026</a>
      <p className="mt-8 text-sm">The isolated demo uses six fictional beneficiary institutions, one hub and two products. All vulnerability indicators are simulated.</p>
    </main>
  );
}

