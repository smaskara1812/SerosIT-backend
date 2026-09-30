using System;
using System.Data;
using System.Configuration;
using System.Collections;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS_Common;
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.IO;
using CrystalDecisions.CrystalReports.Engine;
using CrystalDecisions.Shared;
using System.Collections.Generic;
using System.Net;
using System.Drawing;
using System.Data.OleDb;
using System.Collections.Generic;



public partial class Quality_And_Safety_frmHazard_ID_Card : System.Web.UI.Page
{
    # region User defined variables
    //protected Common_DataRetrival _Common_DataRetrival;
    protected DataSet Ds;
    DataSet DsIncident_Descr = new DataSet();
    SqlConnection Conn;
    SqlDataAdapter Da;
    string strConString = "";
    string strSql = "";
    string ErrorString = "";
    int intImgCnt = 0;
    string[] IMG = new string[10];
    Button[] btnEnableDisable;
    Int16 intMenu_id;
    Int32 intUser_Id;
    public DataTable DtIncident_Img_Path = new DataTable();
    #endregion

    protected string strDebugModeYN = ConfigurationSettings.AppSettings["DebugModeYN"];

    protected void Page_Load(object sender, EventArgs e)
    {
        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass
        //System.Web.UI.WebControls.Button[] btnEnableDisable = new System.Web.UI.WebControls.Button[5];
        //btnEnableDisable[0] = btnAdd;
        //btnEnableDisable[1] = btnUpdate;
        //btnEnableDisable[2] = btnSearch;
        //btnEnableDisable[3] = btnDelete;
        //btnEnableDisable[4] = btnPrint;

        var list = new List<Button>();
        list.Add(btnAdd);
        list.Add(btnUpdate);
        list.Add(btnSearch);
      
        list.Add(btnDelete);
        btnEnableDisable = list.ToArray();
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        string strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));
        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt32(Session["User_Id"].ToString());
        # endregion

        if (!IsPostBack)
        {
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString,"Add");
            Get_Rig();
            GetCompanyName();
            Get_Active_Hazard();
            Get_Vessel_Dept();
        }
        #endregion
         

        #region Depending on selected Employee, fetch the values of Rank field & fill the textboxes
        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
           
            Get_Data_For_Edit();
            tbPostbackFlag_Hidden.Value = "";
            
        }
      
        #endregion
    }

    protected void Get_Rig()
    {
        
        Conn = new SqlConnection(strConString);
        try
        {

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Hazard_ID_Card", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@User_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(intUser_Id);

            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Get_User_Assign_Rigs";
            Da.Fill(Ds, "Rigs");
            if (Ds.Tables["Rigs"].Rows.Count > 0)
            {
                ddlRig.DataSource = Ds.Tables["Rigs"];
                ddlRig.DataValueField = "Rig_Id";
                ddlRig.DataTextField = "Rig_Name";
                ddlRig.DataBind();

            }
            ddlRig.Items.Insert(0, new ListItem("", ""));

        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }

        }
    }


    protected void GetCompanyName()
    {
        Conn = new SqlConnection(strConString);
        try
        {
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            #region Get Offboard_Crew
            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Hazard_ID_Card", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "GetCompanyName";

            if (!string.IsNullOrEmpty(tbHaz_Card_Id_Hidden.Value))
                Da.SelectCommand.Parameters.Add("@Haz_Card_Id", SqlDbType.Int).Value = Convert.ToInt32(tbHaz_Card_Id_Hidden.Value);
            else
                Da.SelectCommand.Parameters.Add("@Haz_Card_Id", SqlDbType.Int).Value = DBNull.Value;

             
            Da.Fill(Ds, "Company_Name");



            while (ddlReported_By_Party.Items.Count > 0)
                ddlReported_By_Party.Items.RemoveAt(0);

            ///Fill the Crew Change Date dropdown 
            if (Ds.Tables["Company_Name"].Rows.Count > 0)
            {
                ddlReported_By_Party.DataSource = Ds.Tables["Company_Name"];
                ddlReported_By_Party.DataTextField = "Name";
                ddlReported_By_Party.DataValueField = "Value";
                ddlReported_By_Party.DataBind();

            }
            #endregion

        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
            }

        }
    }


    protected void Get_Vessel_Dept()
    {
        if (tbRig_Id_Hidden.Value == "")
        {
            return;
        }
        Conn = new SqlConnection(strConString);
        try
        {

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Glo + "Prc_Mst_Vessel_Dept", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@Rig_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbRig_Id_Hidden.Value);         
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select_Dept_Buss_System_6";
            Da.Fill(Ds, "Vessel_Dept");
            if (Ds.Tables["Vessel_Dept"].Rows.Count > 0)
            {
                ddlResponsible_Dept.DataSource = Ds.Tables["Vessel_Dept"];
                ddlResponsible_Dept.DataValueField = "vessel_dept_id";
                ddlResponsible_Dept.DataTextField = "vessel_dept_name";
                ddlResponsible_Dept.DataBind();                
            }
            ddlResponsible_Dept.Items.Insert(0, new ListItem("", ""));
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }
        }
    }

    protected void Get_Vessel_Dept_Wise_Rank()
    {
        ddlResponsible_Rank.DataSource = null;
        ddlResponsible_Rank.DataBind();

        ///In add mode delte the Reported Rank Id 
        ///But in Update mode DONT delete this
        if (tbHaz_Card_Id_Hidden.Value == "")
        {
            tbResp_Rank_Id_Hidden.Value = "";
        }
        if (tbResp_Dept_Id_Hidden.Value == "")
        { 
            return;
        }
        Conn = new SqlConnection(strConString);
        try
        {

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Glo + "Prc_Mst_Vessel_Dept", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;
            ///1)From the rig get the Fs_Category_Id
            ///Pass the category id to get Vessel_Dept_Id 

            Da.SelectCommand.Parameters.Add("@vessel_dept_id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbResp_Dept_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Rig_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbRig_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Get_Rank_From_Vessel_Dept";

            Da.Fill(Ds, "Get_Rank");
            if (Ds.Tables["Get_Rank"].Rows.Count > 0)
            {
                ddlResponsible_Rank.DataSource = Ds.Tables["Get_Rank"];
                ddlResponsible_Rank.DataValueField = "Rank_Id";
                ddlResponsible_Rank.DataTextField = "Rank";
                ddlResponsible_Rank.DataBind();
            }
            ddlResponsible_Rank.Items.Insert(0, new ListItem("", ""));
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();                
            }

        }
    }


    protected void Get_Project_Contract_Dtl()
    {
       
        Conn = new SqlConnection(strConString);
        try
        { 

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Mst_Project_Contract", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            if (tbPostbackFlag_Hidden.Value == "RIG")
            {
                if (tbRig_Id_Hidden.Value == "")
                {
                    ///If user selected Blank then Dont exeecute funtion
                    return;
                }

                ///Add mode
                Da.SelectCommand.Parameters.Add("@Rig_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbRig_Id_Hidden.Value);
                Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Get_Prj_No_Operator_Location_Of_Rig";
            }
            else
            {
                ///udpate mode
                Da.SelectCommand.Parameters.Add("@Prj_Contract_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbPrj_Contract_Id_Hidden.Value);
                Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";
            }
            
            Da.Fill(Ds, "Get_Project_Contract");

            if (Ds.Tables["Get_Project_Contract"].Rows.Count > 0)
            {
                tbPrj_Contract_Id_Hidden.Value = Ds.Tables["Get_Project_Contract"].Rows[0]["Prj_Contract_Id"].ToString();
                tbProject_No_Oper_Location.Text = Ds.Tables["Get_Project_Contract"].Rows[0]["Project_No_Oper_Location"].ToString();
            }
            else
            {
                ScriptManager.RegisterStartupScript(this, this.GetType(), "No_prj_For_Rig", "<script>alert('Project No. is not assigned in master for the selected rig.');</script>", false);
            }
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }

        }
    }
     
    protected void Get_Active_Hazard()
    {
        
        Conn = new SqlConnection(strConString);
        try
        {

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Mst_Hazard_Type", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select_Active_Hazard";
            Da.Fill(Ds, "Active_Hazard");
            if (Ds.Tables["Active_Hazard"].Rows.Count > 0)
            {
                ddlHaz_Type_Name.DataSource = Ds.Tables["Active_Hazard"];
                ddlHaz_Type_Name.DataValueField = "Haz_Type_Id";
                ddlHaz_Type_Name.DataTextField = "Haz_Type_Name";
                ddlHaz_Type_Name.DataBind();
            }

            ddlHaz_Type_Name.Items.Insert(0, new ListItem("", ""));
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }

        }
    }
 
    private void InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum Type)
    {
        clsHazard_ID_Card _ObjMaster = new clsHazard_ID_Card(strConString);

        _ObjMaster.Prj_Contract_Id = Convert.ToInt16(tbPrj_Contract_Id_Hidden.Value);
        _ObjMaster.Rig_Id = Convert.ToInt16(tbRig_Id_Hidden.Value);
        _ObjMaster.Event_Dt = tbEvent_Dt.Text;
        _ObjMaster.Event_Time = tbEvent_Dt_Time.Text;
        //-------------------------------------------------------------------------
        _ObjMaster.Reported_By_Party = ddlReported_By_Party.SelectedValue;
        _ObjMaster.Reported_By_Name = tbReported_By_Name.Text;

        if (tbReported_By_Fs_Emp_Id_Hidden.Value != "")
            _ObjMaster.Reported_By_Fs_Emp_Id = Convert.ToInt32(tbReported_By_Fs_Emp_Id_Hidden.Value);
        else
            _ObjMaster.Reported_By_Fs_Emp_Id = null;
        //-------------------------------------------------------------------------

        _ObjMaster.Work_Location_Id = Convert.ToByte(tbWork_Location_Id_Hidden.Value);
        _ObjMaster.Haz_Type_Id = Convert.ToInt16(tbHaz_Type_Id_Hidden.Value);

        //-------------------------------------------------------------------------
        if(chkTimeout_For_Safety.Checked)
        _ObjMaster.Timeout_For_Safety = "Y";
        else
            _ObjMaster.Timeout_For_Safety = "N";
        //-------------------------------------------------------------------------
        _ObjMaster.Hazard_Desc = tbHazard_Desc.Text;
        _ObjMaster.Action_Taken = tbAction_Taken.Text;
        //-------------------------------------------------------------------------

        _ObjMaster.Resp_Dept_Id = Convert.ToByte(tbResp_Dept_Id_Hidden.Value);
        _ObjMaster.Resp_Rank_Id = Convert.ToByte(tbResp_Rank_Id_Hidden.Value);

        _ObjMaster.Haz_ID_Card_Status = ddlHaz_ID_Card_Status.SelectedValue;
       
        _ObjMaster.Close_Out_Dt = tbClose_Out_Dt.Text;
        _ObjMaster.Close_Out_Dt_Time = tbClose_Out_Dt_Time.Text;
        switch (Type)
        {
            case EBS_Common.Classes.InsertUpdateData_Enum.Insert:
                {             
                    _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.InsertMe();
                    break;
                }
            case EBS_Common.Classes.InsertUpdateData_Enum.Update:
                {                    
                    _ObjMaster.Haz_Card_Id = Convert.ToInt16(tbHaz_Card_Id_Hidden.Value);                   
                    _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                    _ObjMaster.UpdateMe();
                    break;
                }
            case EBS_Common.Classes.InsertUpdateData_Enum.Delete:
                {                     
                    _ObjMaster.Haz_Card_Id = Convert.ToInt16(tbHaz_Card_Id_Hidden.Value);
                    if (tbDeleted_Remarks.Text != "")
                        _ObjMaster.Deleted_Remarks = tbDeleted_Remarks.Text;
                    else
                        _ObjMaster.Deleted_Remarks = null;
                    _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                     
                    _ObjMaster.DeleteMe();
                    break;
                }
        }

        if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
        {
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", _ObjMaster.ErrorString);
            return;
        }
        if (tbPostbackFlag_Hidden.Value == "ADD")
        {
            ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Haz ID Card No.  " + _ObjMaster.Haz_Card_Id.ToString() + "  has been successfully generated', 3500,'',400);</script>", false);
        }
        ClearMe(true);
    } 

    /// <summary>
    /// To clear the text boxes, default selection of combos.
    /// </summary>
    /// <param name="blnClearMainId">Whether to clear Main Id.</param>
    private void ClearMe(bool blnClearMainId)
    {
        if (blnClearMainId == true)
        {
            tbHaz_Card_Id_Hidden.Value = "";
        }

        tbHaz_ID_Card_No.Text = "";
        ///-----------------------------------------------------------------------------------------------------
        tbRig_Id_Hidden.Value = "";
        ddlRig.SelectedValue = "";

        tbPrj_Contract_Id_Hidden.Value = "";
        
        tbProject_No_Oper_Location.Text = "";
        tbProject_No_Oper_Location.Text = "";

        tbEvent_Dt.Text = "";
        tbEvent_Dt_Time.Text = "";
        ///-----------------------------------------------------------------------------------------------------
        ddlReported_By_Party.Enabled = false;
        ddlReported_By_Party.SelectedValue = "";
        tbReported_By_Fs_Emp_Id_Hidden.Value = "";
        tbReported_By_Name.Text = "";

        ///-----------------------------------------------------------------------------------------------------
        tbWork_Location_Id_Hidden.Value = "";
        tbWork_Location_Name.Text = "";

        tbHaz_Type_Id_Hidden.Value = "";
        ddlHaz_Type_Name.SelectedValue = "";

        chkTimeout_For_Safety.Checked = false;
        ///-----------------------------------------------------------------------------------------------------

        tbHazard_Desc.Text = "";
        tbAction_Taken.Text = "";
 
        tbDeleted_Remarks.Text = "";
        ///-----------------------------------------------------------------------------------------------------

        tbResp_Dept_Id_Hidden.Value = "";
        ddlResponsible_Dept.Items.Clear();

        //ddlResponsible_Dept.SelectedValue = "";
        //ddlResponsible_Dept.DataSource = null;
        //ddlResponsible_Dept.DataBind();

        tbResp_Rank_Id_Hidden.Value = "";
        ddlResponsible_Rank.Items.Clear();

        //ddlResponsible_Rank.DataSource = null;
        //ddlResponsible_Rank.DataBind();
        //ddlResponsible_Rank.SelectedValue = "";

        tbClose_Out_Dt.Text = "";
        tbClose_Out_Dt_Time.Text = "";
        ///------------------------------------------------------------------------------------------------------------
        ddlHaz_ID_Card_Status.SelectedValue  = "O";

        ///------------------------------------------------------------------------------------------------------------
        
        ddlRig.Enabled = true;
         

        tbEvent_Dt.CssClass = "textbox";
        tbEvent_Dt.Attributes.Remove("OnKeyDown");
    
        tbEvent_Dt_Time.CssClass = "textbox";
        tbEvent_Dt_Time.Attributes.Remove("OnKeyDown");

        ddlReported_By_Party.Enabled = true;
        ibtnFs_Emp_Name.Visible = true;
        //tbReported_By_Name.CssClass  IN JS
        ibtnWork_Location.Visible = true;
        ddlHaz_Type_Name.Enabled = true;
        chkTimeout_For_Safety.Enabled = true;

        tbHazard_Desc.CssClass = "textbox";
        tbHazard_Desc.Attributes.Remove("OnKeyDown");

        tbAction_Taken.CssClass = "textbox";
        tbAction_Taken.Attributes.Remove("OnKeyDown");

        ddlResponsible_Dept.Enabled = true;
        ddlResponsible_Rank.Enabled = true;

        tbClose_Out_Dt.CssClass = "textbox";
        tbClose_Out_Dt.Attributes.Remove("OnKeyDown");

        tbClose_Out_Dt_Time.CssClass = "textbox";
        tbClose_Out_Dt_Time.Attributes.Remove("OnKeyDown");

        ddlHaz_ID_Card_Status.Enabled = true;
        tbHaz_ID_Card_Status_Hidden.Value = "";

        GetCompanyName();
        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");
    }

    protected void btnAdd_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Insert);
    } 

    protected void Get_Data_For_Edit()
    {
        ClearMe(false);

        GetCompanyName();
   

        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");
  
        Conn = new SqlConnection(strConString);
        try
        {
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_Hazard_ID_Card", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@Haz_Card_Id", SqlDbType.Int).Value = Convert.ToInt16(tbHaz_Card_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";
            Da.Fill(Ds, "Data_For_Edit");

            tbHaz_ID_Card_No.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Haz_ID_Card_No"].ToString();
            ///-----------------------------------------------------------------------------------------------------
            tbPrj_Contract_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Prj_Contract_Id"].ToString();
             

            tbRig_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Id"].ToString();
            ddlRig.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Id"].ToString();

            tbEvent_Dt.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Event_Dt"].ToString();
            tbEvent_Dt_Time.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Event_Dt_Time"].ToString();

            ddlReported_By_Party.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Reported_By_Party"].ToString();


            tbReported_By_Fs_Emp_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Reported_By_Fs_Emp_Id"].ToString();
            tbReported_By_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Reported_By_Name"].ToString();

            tbWork_Location_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Work_Location_Id"].ToString();
            tbWork_Location_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Work_Location"].ToString();

            tbHaz_Type_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Haz_Type_Id"].ToString();
            ddlHaz_Type_Name.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Haz_Type_Id"].ToString();

            tbHaz_ID_Card_Status_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Haz_ID_Card_Status"].ToString();
             
            if (Ds.Tables["Data_For_Edit"].Rows[0]["Timeout_For_Safety"].ToString() == "Y")
            {
                chkTimeout_For_Safety.Checked = true;
            }
            else
            {
                chkTimeout_For_Safety.Checked = false;
            }

            tbHazard_Desc.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Hazard_Desc"].ToString();
            tbAction_Taken.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Action_Taken"].ToString();

            tbClose_Out_Dt.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Close_Out_Dt"].ToString();
            tbClose_Out_Dt_Time.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Close_Out_Dt_Time"].ToString();
            ///--------------------------------------------------------------------------------------
           
            tbResp_Dept_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Resp_Dept_Id"].ToString();
            ddlResponsible_Dept.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Resp_Dept_Id"].ToString();

            tbResp_Rank_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Resp_Rank_Id"].ToString();

            ddlHaz_ID_Card_Status.SelectedValue = Ds.Tables["Data_For_Edit"].Rows[0]["Haz_ID_Card_Status"].ToString();


            if (ddlReported_By_Party.SelectedValue == "EOSIL")
            {
                ddlReported_By_Party.Enabled = false;
            }
            Get_Vessel_Dept();
            
            Get_Vessel_Dept_Wise_Rank();
            ddlResponsible_Rank.SelectedValue = tbResp_Rank_Id_Hidden.Value;
            Get_Project_Contract_Dtl();
            ///------------------------------ Compulsary Disable---------------------------------------------------
            //ddlRig.Enabled = false;

            //tbEvent_Dt.CssClass = "textbox_readonly";
            //tbEvent_Dt.Attributes.Add("OnKeyDown", "return RejectInput()");

            //tbEvent_Dt_Time.CssClass = "textbox_readonly";
            //tbEvent_Dt_Time.Attributes.Add("OnKeyDown", "return RejectInput()");
            //ibtnPrj_Contract.Visible = false;
              
            ///--------------------------------------------------------------------------------------
            /// 

            if (tbHaz_ID_Card_Status_Hidden.Value  == "O")
            {
            }
            else///Closed
            {
                ddlRig.Enabled = false;

                tbEvent_Dt.CssClass = "textbox_readonly";
                tbEvent_Dt.Attributes.Add("OnKeyDown", "return RejectInput()");

                tbEvent_Dt_Time.CssClass = "textbox_readonly";
                tbEvent_Dt_Time.Attributes.Add("OnKeyDown", "return RejectInput()");
                
                 
                ddlReported_By_Party.Enabled = false;
                ibtnFs_Emp_Name.Visible = false;
                //tbReported_By_Name.CssClass   IN JS
                ibtnWork_Location.Visible = false;
                ddlHaz_Type_Name.Enabled = false;
                chkTimeout_For_Safety.Enabled = false;

                tbHazard_Desc.CssClass = "textbox_readonly";
                tbHazard_Desc.Attributes.Add("OnKeyDown", "return RejectInput()");


                tbAction_Taken.CssClass = "textbox_readonly";
                tbAction_Taken.Attributes.Add("OnKeyDown", "return RejectInput()");

                ddlResponsible_Dept.Enabled = false;
                ddlResponsible_Rank.Enabled = false;

                tbClose_Out_Dt.CssClass = "textbox_readonly";
                tbClose_Out_Dt.Attributes.Add("OnKeyDown", "return RejectInput()");

                tbClose_Out_Dt_Time.CssClass = "textbox_readonly";
                tbClose_Out_Dt_Time.Attributes.Add("OnKeyDown", "return RejectInput()");

                ddlHaz_ID_Card_Status.Enabled = false;


                btnUpdate.Enabled = false;
                btnDelete.Enabled = false;
                 

                ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup('Hazard ID is closed , Cannot Update/Delete', 2000);</script>", false);
         
            }
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();                
            }
        }
    }

    protected void btnClear_Click(object sender, EventArgs e)
    {
        ClearMe(true);
    }

    protected void btnUpdate_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Update);
    }
      
    protected void btnDelete_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Delete);
    }


    protected void ddlResponsible_Dept_SelectedIndexChanged(object sender, EventArgs e)
    {
        //clear value of the dependent fields
        tbResp_Rank_Id_Hidden.Value = "";

        tbResp_Dept_Id_Hidden.Value = ddlResponsible_Dept.SelectedValue;
        Get_Vessel_Dept_Wise_Rank();
        

    }
    protected void ddlRig_SelectedIndexChanged(object sender, EventArgs e)
    {
        ddlResponsible_Rank.Items.Clear();
        tbResp_Dept_Id_Hidden.Value ="";
        tbResp_Rank_Id_Hidden.Value = "";
        tbPrj_Contract_Id_Hidden.Value = "";


        Get_Project_Contract_Dtl();
        Get_Vessel_Dept();
        Get_Vessel_Dept_Wise_Rank();
        tbPostbackFlag_Hidden.Value = "";
    }
    protected void btnDelete_Ok_Final_Click(object sender, EventArgs e)
    {
        InsertUpdateData(EBS_Common.Classes.InsertUpdateData_Enum.Delete);
    }
}