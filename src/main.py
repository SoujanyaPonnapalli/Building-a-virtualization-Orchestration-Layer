# arguments - pm_file, image_file, vm_types
import sys, uuid, json, subprocess, os, libvirt
from flask import Flask, request, jsonify
app = Flask(__name__)

machinesList = []
imagesList = []
vm_list = []
pmid = 0
vmid = 0
pm_details = []

def create_xml(vm_name, hypervisor, uid, path, ram, cpu, arch_type):
	xml = r"<domain type='" + hypervisor + \
		"'><name>" + vm_name + "</name> \
		<memory>" + ram + "</memory> \
		<uuid>" + uid + "</uuid> \
		<vcpu>" + cpu + "</vcpu> \
		<os> \
		<type arch='" + arch_type + "' machine='pc'>hvm</type> \
		<boot dev='hd'/> \
		</os> \
		<features> \
		<acpi/> \
		<apic/> \
		<pae/> \
		</features> \
		<on_poweroff>destroy</on_poweroff> \
		<on_reboot>restart</on_reboot> \
		<on_crash>restart</on_crash> \
		<devices> \
		<disk type='file' device='disk'> \
		<source file='" + path + "'/> \
		<target dev='hda' bus='ide'/> \
		<address type='drive' controller='0' bus='0' unit='0'/> \
		</disk> \
		</devices> \
		</domain>"
	return xml

def machines(File):
	global machinesList
	fp = open(File)
	content = fp.readlines()
	ID = 1
	for each in content:
		each = each[:-1]
		List = each.split('@')
		List.append(uuid.uuid4())
		List.append(ID)
		ID += 1
		machinesList.append(List)

def images(File):
	global imagesList
	fp = open(File)
	content = fp.readlines()
	Image_ID = 1
	for each in content:
		each = each[:-1]
		List = each.split('@')
		temp = List[1].split(':')
		List[1] = temp[0]
		List.append(Image_ID)
		List.append(temp[1])
		imagesList.append(List)
		Image_ID += 1

def scp_image_path(arg):
	user = imagesList[arg-1][0]
	ip = imagesList[arg-1][1]
	path = imagesList[arg-1][3]
	os.system("scp " + user + "@" + ip + ":" + path + " ~/")

def types(File):
	global Dict
	fp = open(File)
	content = fp.readlines()
	temp = unicode(''.join(map(lambda each: each.strip(), content)))
	Dict = json.loads(temp)

@app.route('/server/vm/create/', methods = ['GET'])
def create():
	instance_type = int(request.args.get('instance_type'))
	name = request.args.get('name')
	image_id = request.args.get('image_id')

	global pmid, vmid, vm_list
	machine = machinesList[pmid]
	user = machine[0]
	ip = machine[1]
	vcpu = Dict['types'][instance_type-1]['cpu']
	Ram = Dict['types'][instance_type-1]['ram']
	Ram = Ram * 1024
	
	avail_cpu = int(subprocess.check_output("ssh " + user + "@" + ip + ' nproc',shell=True))
	free_space = (subprocess.check_output("ssh " + user + "@" + ip + " free -m" ,shell=True))
	
	free_space = free_space.split("\n")
	free_space = free_space[1].split()
	avail_ram = int(free_space[3]) * 1024
	
	check_arch = (((imagesList[int(image_id)-1])[-1]).split('/')[-1]).split('.')[0].split('_')[1]

	tot = 1
	while(avail_cpu < vcpu or avail_ram < Ram):
		pmid = (pmid + 1)%(len(machinesList))
		tot = tot + 1
		if(tot > len(machinesList)):
			return jsonify({"Error" : " Specifications could not be satisfied, Virtual Machine cannot be created"})
		machine = machinesList[pmid]
		user = machine[0]
		ip = machine[1]
		avail_cpu = int(subprocess.check_output("ssh " + user + "@" + ip + " nproc" ,shell=True))
		free_space = (subprocess.check_output("ssh " + user + "@" + ip + " free -m" ,shell=True))
		free_space = free_space.split("\n")[1].split()
		avail_ram = int(free_space[3]) * 1024
		check_arch = (((imagesList[int(image_id)-1])[-1]).split('/')[-1]).split('.')[0].split('_')[1]
	
	vmid = vmid + 1
	vm_list.append([vmid, name, instance_type, pmid])

	temp_dict = {}
	temp_dict['pmid'] = pmid
	temp_dict['capacity'] = {'cpu': vcpu, 'ram': Ram}
	temp_dict['free'] = {'cpu': avail_cpu, 'ram': avail_ram}
	global p_machines_list
	pm_details.append(temp_dict)
	#print temp_dict, pm_details

	pmid = (pmid + 1)%(len(machinesList))
	uid = str(uuid.uuid4())

	scp_image_path(int(image_id))
	Image_name = (((imagesList[int(image_id)-1])[-1]).split('/')[-1])
	Image_path = "/home/" + user + "/Desktop/" + Image_name
	os.system("scp ~/" + Image_name + " " + user + "@" + ip + ":" + Image_path)

	#remote+ssh://soujanya@10.1.99.140/
	path = 'remote+ssh://' + user + '@' + ip + '/'
	connect = libvirt.open(path)
	system_info = connect.getCapabilities()
	arch_type = system_info.split("<arch>")
	arch_type = arch_type[1].split("<")[0] #archituctue of machine
	req = connect.defineXML(create_xml(name, connect.getType().lower(), uid, Image_path, str(Ram), str(vcpu), arch_type))
	try:
		req.create()
		return jsonify({"vmid": vmid})
	except:
		return jsonify({"vmid" : 0 })
	return jsonify({})

@app.route('/server/vm/query/', methods = ['GET'])
def get_info():
	vmid = int(request.args.get('vmid'))
	List = {}
	try:
		for i in vm_list:
			if i[0] == vmid:
				List['vmid'] = i[0]
				List['name'] = i[1]
				List['instance_type'] = i[2]
				List['pmid'] = i[3] + 1
				break
		return jsonify(List)
	except:
		return jsonify(List)

@app.route('/server/vm/destroy/', methods = ['GET'])
def destroy():
	vmid = int(request.args.get('vmid'))
	#print vm_list
	try:
		cnt = 0
		for i in vm_list:
			if i[0] == vmid:
				break
			cnt = cnt + 1
		machine = machinesList[i[3]]
		user = machine[0]
		ip = machine[1]
		
		path = 'remote+ssh://' + user + '@' + ip + '/'
		connect = libvirt.open(path)
		req = connect.lookupByName(i[1])
		
		if req.isActive():
			#print "Yes, Active domain!"
			req.destroy()
		req.undefine()
		del vm_list[cnt]
		return jsonify({"status":"success"})
	except:
		return jsonify({"status":"failed"})

@app.route('/server/vm/types/', methods = ['GET'])
def Types():
	return jsonify(Dict)

@app.route('/server/pm/list', methods = ['GET'])
def p_machines_list():
	List = []
	try:
		for i in vm_list:
			List.append(i[3] + 1)
		return jsonify({"pmids": List})
	except:
		return jsonify({"pmids" :List})

@app.route('/server/pm/listvms', methods = ['GET'])
def virt_machines_list():
	pmid = int(request.args.get('pmid'))
	List = []
	try:
		for i in vm_list:
			if i[3] == pmid:
				List.append(i[0])
		return jsonify({"vmids": List})
	except:
		return jsonify({"pmid" : "Invalid pmid"})
	
@app.route('/server/pm/query', methods = ['GET'])
def p_machine_details():
	pmid = int(request.args.get('pmid'))

	return jsonify({'details' : pm_details})

@app.route('/server/image/list', methods = ['GET'])
def image_details():
	returnDict = {}
	List = []
	for each in imagesList:
		temp = {}
		path = each[3]
		Id = each[2]
		image = path.split('/')[-1]
		temp['id'] = Id
		temp['name'] = image
		List.append(temp)

	returnDict['images'] = List
	return jsonify(returnDict)

if __name__ == '__main__':
	if len(sys.argv) < 4:
		print "Format is python script.py pm_file image_file vm_types"
		exit(1)

	machines(sys.argv[1])
	images(sys.argv[2])
	types(sys.argv[3])

	app.run(debug = True)
