**Prancer** has its own set of terms that need to be understood before you dwelve deeper into it. Take time to understand each concept properly before going on.

# Providers & connectors

A **provider** is a system which provides data to **Prancer**. For example:

- Azure
- Amazon Web Services
- Google Cloud
- Filesystem

A **connector** file is used to connect to those providers and extract data from them that will be used to take the snapshot and in testing scenarios. Each connector has its own configuration file that details the credentials (if applicable) and location of the provider to represent.

# Monitored resources & snapshots

A **monitored resource**, is an item that you want **Prancer** to observe and validate. This resource could be in the cloud or in a file. You define monitored resources through a **snapshot configuration** file.

A **snapshot configuration** file is used to define what you want to observe. It will use a **connector** that you previously configured to get a representation of a **monitored resource** on the referenced **provider**. By using different **connectors**, you can gather a broad snapshot of your different systems and then run tests on this data.

A **master snapshot configuration** file is used to define the type of resources you want to observe. The **crawler** processor uses the **master snapshot configuration** file to find new resources in the target environment based on the **connector** file.

When you gather data about your **monitored resources** you are creating **snapshots**. **snapshots** are actual represantation of **monitored resources** in json format. These **snapshots** are kept in a file system or database over time so you can track the changes if anything happens. You then run tests on those **snapshots** to validate that your infrastructure (but also files) are still healthy.

# Tests, rules & reports

**Prancer** uses **tests** to validate your infrastructure. A **test** uses a **snapshot configuration** to figure out what to run the tests over. a **test file** contains various test cases to run against the **monitored resources**.

**Rules** are an important part of a **test**. **Rules** define what needs to be tested. **Prancer** uses a custom domain specific language (DSL) that looks a lot like **Javascript** to run tests. The **rules** comparison engine runs against a **monitored resource**'s **snapshot** and checks the values collected against other values (static or dynamic) to validate your infrastructure or files.

A **Master test** file is a test file in the prancer cloud validation framework which defines test cases for different **type** of monitored resources rather than individual resources. A master test file works in tandem with the **master snapshot configuration** file to run test cases on different type of resources.

When **Prancer** runs tests, it generates an **output** for every test file. All the test cases available in a test file will be evaluated and a result will be saved to this report file so you can put them in an artifact system for later reference.

# Projects

A **project** is a set of configuration files that can be commited to a version control system alongside of your project. Example of such files:

* Project configuration
* Connector configuration
* Snapshot configuration
* Test file

These files should follow your development project that would usually contain **infrastructure as code** files such as:

* **AWS CloudFormation** templates
* **Azure ARM** templates
* **Terraform** scripts
* etc

With those two elements in place, **Prancer** can be used to validate the files **before** applying them and can also be used **after** applying them directly on the provider of your choice.

# Containers

**Containers** are simple folders that allow you to group your snapshots and tests together in a logical way to help you better manage your different tests, infrastructure components and results.