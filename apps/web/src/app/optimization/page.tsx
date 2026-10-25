import OptimizationDesk from "./optimization-desk";
import "./optimization.css";

export default async function OptimizationPage({
  searchParams,
}: {
  searchParams: Promise<{ job?: string }>;
}) {
  const { job } = await searchParams;
  return <OptimizationDesk initialJobId={job ?? null} />;
}
