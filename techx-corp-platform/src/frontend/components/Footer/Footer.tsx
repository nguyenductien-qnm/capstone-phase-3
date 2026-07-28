import { useEffect, useState } from 'react';
import SessionGateway from '../../gateways/Session.gateway';
import { CypressFields } from '../../utils/enums/CypressFields';
import PlatformFlag from '../PlatformFlag';

const currentYear = new Date().getFullYear();
const { userId } = SessionGateway.getSession();

const Footer = () => {
  const [sessionId, setSessionId] = useState('');
  useEffect(() => { setSessionId(userId); }, []);

  return (
    <footer className="border-t border-border bg-muted/30 mt-auto">
      <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-center text-sm text-muted-foreground sm:flex-row sm:justify-between sm:px-6 lg:px-8">
        <p>This website is hosted for demo purpose only. It is not an actual shop.</p>
        <p><span data-cy={CypressFields.SessionId}>session-id: {sessionId}</span></p>
        <p>@{currentYear} TechX Corp</p>
        <PlatformFlag />
      </div>
    </footer>
  );
};

export default Footer;
