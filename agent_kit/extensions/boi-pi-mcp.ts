// Provider transport only: the existing Wiki MCP endpoints retain authority.
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { StringDecoder } from 'node:string_decoder';

export default async function boiPiMcp(pi: any) {
  const configPath = process.env.BOI_PI_MCP_CONFIG;
  if (!configPath) throw new Error('BOI_PI_MCP_CONFIG_REQUIRED');
  const config = JSON.parse(readFileSync(configPath, 'utf8'));
  const child = spawn(config.python, ['-m', 'agent_kit.python.boi_pi_mcp', '--config', configPath], {
    cwd: config.repository, env: process.env, stdio: ['pipe', 'pipe', 'pipe'],
  });
  let counter = 0, buffer = '', failed: Error | null = null;
  const decoder = new StringDecoder('utf8');
  const pending = new Map<string, {resolve: Function, reject: Function}>();
  const fail = (error: Error) => {
    failed = error;
    for (const waiter of pending.values()) waiter.reject(error);
    pending.clear();
  };
  child.stdout.on('data', chunk => {
    buffer += decoder.write(chunk);
    let cut: number;
    while ((cut = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, cut); buffer = buffer.slice(cut + 1);
      try {
        const value = JSON.parse(line);
        const waiter = pending.get(value.id);
        if (!waiter) throw new Error('PI_MCP_RESPONSE_ID_INVALID');
        pending.delete(value.id);
        if (value.success) waiter.resolve(value.result);
        else waiter.reject(new Error('PI_MCP_CALL_FAILED:'+value.error));
      } catch (error) { fail(error as Error); child.kill('SIGTERM'); }
    }
  });
  child.on('error', fail);
  child.stdin.on('error', fail);
  child.stderr.resume(); // MCP libraries may log; never expose credentials through stderr.
  child.on('exit', () => fail(new Error('PI_MCP_BRIDGE_EXITED_NO_AUTOMATIC_RETRY')));
  const request = (body: object) => new Promise<any>((resolve, reject) => {
    if (failed) { reject(failed); return; }
    const id = String(++counter); pending.set(id,{resolve,reject});
    child.stdin.write(JSON.stringify({id,...body})+'\n');
  });
  const stop = () => { child.stdin.end(); child.kill('SIGTERM'); };
  pi.on('session_shutdown', stop);
  process.once('exit', stop);
  const inventory = await request({type:'list_tools'});
  for (const tool of inventory.tools) {
    pi.registerTool({
      name:tool.name, label:tool.name, description:tool.description,
      parameters:tool.inputSchema,
      async execute(_id: string, arguments_: object) {
        const result = await request({type:'call_tool',name:tool.name,arguments:arguments_});
        if (result.isError) throw new Error(JSON.stringify({error:'MCP_TOOL_FAILED',content:result.content}));
        // Keep original MCP content and full structured result; no generated prose.
        return {content:result.content ?? [{type:'text',text:JSON.stringify(result)}],details:result};
      },
    });
  }
}
