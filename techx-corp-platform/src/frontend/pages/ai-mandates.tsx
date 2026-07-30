import Head from 'next/head';
import Layout from '../components/Layout';
import MandateExperience from '../components/MandateExperience/MandateExperience';

export default function AiMandatesPage() {
  return (
    <Layout>
      <Head>
        <title>AI Mandates | TechX Corp</title>
        <meta name="description" content="Live evidence for TechX AI evaluation, memory, observability and resilience mandates." />
      </Head>
      <MandateExperience />
    </Layout>
  );
}
